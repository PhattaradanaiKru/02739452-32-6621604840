# ผลการตรวจระบบจริง

ตรวจเมื่อ 23 ตุลาคม 2026 บน Docker Desktop (Linux engine) โดยรัน Airflow 2.10.4 / CeleryExecutor ตามโครงของอาจารย์ ผลนี้เป็นการตรวจ local checkout ไม่ใช่การยืนยันว่าโค้ดถูก push ไป GitHub แล้ว

## ข้อมูลรอบ submission_verified

- DAG success, 23 ต.ค. 2026 เวลา 13:58:53 - 13:59:43 น. เวลาไทย (Airflow แสดง UTC)
- GeoNames: 810 ADM2 candidate records จาก HTML; e-Stat: 791 city population records; UNdata: 262 city-proper records
- หลังรวมและตรวจคุณภาพ: **779 เมืองไม่ซ้ำ ครอบคลุม 47 จังหวัด**
- **768 เมืองมีประชากรปี 2020** อีก 11 เมืองใช้ประชากร GeoNames ที่ไม่ระบุปี
- default Dashboard จึงแสดง 768 เมือง เนื่องจากเลือก Census 2020; เลือก All population years เพื่อดูครบ 779 เมือง
- rejected 69 source/merged records ไม่ใช่จำนวนเมืองที่หายไปทั้งหมด เนื่องจาก records มาจากคนละแหล่งและหนึ่งเมืองมีหลาย observations
- มี 779 แถวใน cities และ 1,778 แถวใน population_observations (รวมประวัติที่เก็บไว้; records ของรอบล่าสุด 1,777 แถว)

## ผลทดสอบ

| ตรวจ | ผล |
|---|---|
| Unit tests 8 กรณี | ผ่าน ทั้งบน bundled Python และ Python ใน container |
| DAG import errors | ไม่มี |
| HTTP health / PostgreSQL direct query | ผ่าน |
| ค้นหาและกรอง Hokkaido + ปี 2020 | ผ่าน |
| CSV export ตรงกับตัวกรอง | ผ่าน |
| รายละเอียดเมืองและ 404 สำหรับ ID ที่ไม่มี | ผ่าน |
| SQL parameters ด้วย input `' OR 1=1 --` | ไม่ขยายผลค้นหา ไม่ได้ต่อ input เข้า SQL |
| UPSERT ซ้ำ batch เดิม | ก่อนและหลัง 779 เมือง / 1,778 observations เท่ากัน |
| ตั้ง quality threshold 99,999 จาก batch จริงที่ replay | บล็อก publish; จำนวนเมืองและผลรวมประชากรเดิมไม่เปลี่ยน |
| Browser QA | ค้น Sapporo เหลือ 1 เมือง, เปิดรายละเอียดเทียบแหล่ง, Reset คืนค่าเริ่มต้น, เปิด Pipeline status ได้ |

## จำลอง outage ผ่าน Airflow worker จริง

ใช้ `dag_run.conf.disabled_sources` ให้ extractor ของแหล่งที่เลือกยก exception จริง มี retry และแสดงสี failed ใน Grid จากนั้น merge ที่ใช้ all_done ทำงานต่อ

| Run ID | ปิดแหล่ง | ผลในฐาน target | เมือง |
|---|---|---|---:|
| validation_source_outage | UNdata | degraded | 779 |
| validation_geonames_outage | GeoNames | degraded, ใช้พิกัดเดิมและเวลาดึงเดิม | 768 |
| validation_estat_outage | e-Stat | degraded | 729 |
| validation_all_sources_outage | ทุกแหล่ง | quality_failed; ไม่ทับ published data | 0 ใหม่ |
| submission_verified | ไม่ปิด | success, ครบ 3 แหล่ง | 779 |

พิกัดเดิมใช้ได้เมื่อเคยรันสำเร็จเท่านั้น ฐานใหม่ที่ GeoNames ล่มอาจไม่ผ่านเกณฑ์เพราะไม่มีพิกัด ไม่สร้างข้อมูลแทนค่า missing และไม่อ้างว่า latest source failed เป็น source success

## ปัญหาจริงและการแก้

1. Docker CLI มีอยู่ แต่ engine ยังไม่ทำงาน: `docker info` หา named pipe ไม่เจอ จึงเริ่ม Docker Desktop แล้วตรวจ engine ก่อนเปิด compose
2. GeoNames หน้ารวมเมืองใหญ่มีเพียง 12 เมือง และ robots.txt ของ download host ไม่ให้ crawler: ตรวจ HTML กับ robots ของแต่ละ host แล้วเปลี่ยนไป scraping search HTML แบบแบ่งหน้า ซึ่งอนุญาต แทนเส้นทางดาวน์โหลด
3. กรองชื่อเมืองด้วย Shi อย่างเดียวทำให้เมืองใหญ่ตกหล่น: ตรวจ raw HTML พบ Yokohama / Nagoya / Kyoto ไม่จำเป็นต้องมี suffix ใน primary name จึงใช้ ADM2 candidate แล้วให้ข้อมูลทางการยืนยันประเภทเมือง ได้ 779 เมืองแทน 677 ในรอบแรก
4. เมืองชื่อซ้ำอาจจับคู่ UNdata ผิด: เพิ่มจังหวัดใน key สำหรับ e-Stat และไม่จับคู่ UNdata ที่กำกวม เว้นแต่มีประชากรปีเดียวกันตรงกันพอดีเพียงเมืองเดียว ทดสอบกรณี Date ในสองจังหวัด

## หลักฐาน

ภาพใน `reports/evidence/` เป็น screenshot ของระบบที่รันจริง: Dashboard, Graph view, Grid view และหน้าสถานะ pipeline รายงาน PDF ใช้ภาพตัดเฉพาะส่วนเพื่อให้อ่านชัด โดยไม่สร้างสถานะงานขึ้นใหม่

ข้อจำกัด: ไม่ครอบคลุมทุกเทศบาล ญี่ปุ่นมีชื่อ romanization หลายแบบที่ยังไม่จับคู่ พิกัด GeoNames เป็น reference point ของเทศบาลไม่ใช่ city center ทุกเมือง ข้อมูล HTML ต้นทางอาจเปลี่ยนได้ ต้องตรวจโครงสร้างและจำนวน records เมื่อรันใหม่

## ปรับเป็นภาษาไทย

- แปลหน้าเว็บทั้ง 4 ส่วน รวมตัวกรอง กราฟ ตาราง รายละเอียดเมือง สถานะ ข้อผิดพลาด และเหตุผลที่ไม่ผ่านคุณภาพ
- แสดงชื่อจังหวัดภาษาไทยครบ 47 จังหวัด โดยรักษาค่าที่ใช้กรองและชื่อเมืองต้นฉบับไว้ ตัวเลขประชากรและชุดข้อมูลไม่เปลี่ยน
- แสดงวันเวลาตามรูปแบบไทยและเขตเวลา Asia/Bangkok โดยปีข้อมูลประชากรยังเป็น ค.ศ. 2020
- สร้าง PDF ภาษาไทย 3 หน้า พร้อมภาพหน้าเว็บภาษาไทย จัดรูปสระวรรณยุกต์ด้วย HarfBuzz และตัดคำด้วย PyThaiNLP ตรวจภาพเรนเดอร์ครบทุกหน้า
- ตรวจ API, ตัวกรอง, รายละเอียดเมือง และ CSV หลังปรับภาษาแล้ว ผ่านตามเดิม
