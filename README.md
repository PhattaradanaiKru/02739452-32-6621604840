# Japan City Atlas

ระบบรวบรวมข้อมูลประชากรและพิกัดเมืองในประเทศญี่ปุ่นอย่างน้อย 100 เมือง ด้วย Apache Airflow จัดเก็บใน PostgreSQL และแสดงผลบนเว็บ Dashboard

รายวิชา 02739452 | ลำดับที่ 32 | รหัสนิสิต 6621604840

## แหล่งข้อมูล

| แหล่งข้อมูล | ข้อมูลและวิธีดึง |
|---|---|
| [GeoNames](https://www.geonames.org/search.html?q=shi&country=JP&featureClass=A&maxRows=500) | ดึง HTML ด้วย requests และ BeautifulSoup แบบแบ่งหน้า เพื่อรวบรวมชื่อเมือง รหัสเมือง และพิกัดละติจูด/ลองจิจูด |
| [e-Stat](https://dashboard.e-stat.go.jp/en/) | เรียก public JSON API เพื่อรวบรวมประชากรสำมะโนปี 2020 รหัสเทศบาล และจังหวัด โดยไม่ต้องใช้ API key |
| [UNdata](https://data.un.org/Data.aspx?d=POP&f=tableCode%3A240%3BcountryCode%3A392%3BrefYear%3A2020%3BsexCode%3A0) | ดึง HTML ตารางประชากรด้วย requests และ BeautifulSoup กรองญี่ปุ่น ปี 2020 ทุกเพศ และขอบเขตตัวเมือง เพื่อเปรียบเทียบและเสริมข้อมูลประชากร |

รวมข้อมูลระดับเทศบาลเมือง ไม่รวมจังหวัด เขตย่อย และหมู่บ้าน เลือกประชากรจาก e-Stat ก่อน UNdata และ GeoNames ตามลำดับ โดย GeoNames บางรายการไม่ระบุปีประชากร ตรวจ robots.txt และจำกัดความถี่ในการดึงข้อมูล ไม่ใช้ Selenium และไม่เก็บข้อมูลส่วนบุคคล

ข้อมูลพิกัดจาก GeoNames ใช้ภายใต้ [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## วิธีรัน

เตรียม Git, Python 3 และ Docker Desktop ที่เปิด Linux engine พร้อม Docker Compose แนะนำ RAM สำหรับ Docker อย่างน้อย 8 GB และอินเทอร์เน็ตสำหรับดึงข้อมูล

```powershell
git clone https://github.com/PhattaradanaiKru/02739452-32-6621604840.git
cd 02739452-32-6621604840
python scripts/setup_env.py
docker compose build airflow-init
docker compose up -d
```

สคริปต์จะสร้าง `.env` พร้อมรหัสผ่านสุ่มสำหรับเครื่อง โดยไม่ทับไฟล์เดิม ใช้ `.env.example` เป็นตัวอย่างการตั้งค่า

1. เปิด Airflow ที่ [localhost:8080](http://localhost:8080) เข้าระบบด้วยชื่อผู้ใช้ `airflow` และรหัสผ่าน `AIRFLOW_PASSWORD` จาก `.env`
2. เปิดสวิตช์ DAG `japan_city_pipeline` แล้วกด **Trigger DAG** หรือใช้คำสั่งนี้:

```powershell
docker compose exec airflow-scheduler airflow dags unpause japan_city_pipeline
docker compose exec airflow-scheduler airflow dags trigger japan_city_pipeline
```

3. รอให้งาน `publish` สำเร็จ แล้วเปิด Dashboard ที่ [localhost:8000](http://localhost:8000) หากเปิดเว็บไว้ก่อน ให้รีเฟรชหน้าเว็บเพื่อโหลดข้อมูล

หน้าเว็บเริ่มต้นเลือกประชากรปี 2020 สามารถค้นหา กรองข้อมูล ดูพิกัดและกราฟประชากร หรือดาวน์โหลด CSV ได้

ตรวจสถานะและดูบันทึกเมื่อมีปัญหา:

```powershell
docker compose ps
docker compose logs --tail=80 airflow-scheduler airflow-worker web
```

หยุดระบบด้วย `docker compose stop` และเปิดใหม่ด้วย `docker compose up -d` ข้อมูลยังอยู่ใน Docker volumes หากพอร์ตชนกับงานอื่น ให้แก้ `AIRFLOW_PORT`, `WEB_PORT` หรือ `TARGET_PORT` ใน `.env`
