# ⛳ ITECH@BalanceX (ระบบบัญชีคู่ Double-Entry)

ระบบจัดการบัญชีคู่ (Double-Entry Accounting) ที่ถูกออกแบบมาให้ใช้งานง่าย รวดเร็ว และทำงานผ่าน Web Application ด้วย Python (Flask)

## ✨ ฟีเจอร์หลัก (Features)
- **ระบบสมุดรายวันทั่วไป (Journal Entry):** บันทึกเดบิต/เครดิต ได้ไม่จำกัดบรรทัด และตรวจสอบความสมดุล (Balance) อัตโนมัติ
- **สมุดบัญชีแยกประเภท (General Ledger - GL):** เรียกดูความเคลื่อนไหวรายบัญชีได้ทันที
- **งบทดลอง (Trial Balance - TB):** สรุปยอดคงเหลือของทุกบัญชี
- **ระบบสำรองข้อมูล (Google Sheets Sync):** ยิงข้อมูลไปเก็บที่ Google Sheets แบบ Real-time ทันทีที่กดบันทึก (ผ่าน Webhook)
- **ระบบออกรายงาน (Export & Print):** สามารถพิมพ์เอกสารหน้าเว็บ (ตั้งค่าซ่อนเมนูอัตโนมัติ) และดาวน์โหลดข้อมูลเป็นไฟล์ Excel (`.xlsx`)
- **ระบบรักษาความปลอดภัย (Security):** ล็อคหน้าเว็บด้วยรหัสผ่านก่อนเข้าใช้งาน

---

## 💻 การติดตั้งและรันบนเครื่องส่วนตัว (Local Development - Windows)

1. **สร้าง Virtual Environment และติดตั้งไลบรารี:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **รันเซิร์ฟเวอร์จำลอง:**
   ```bash
   python app.py
   ```
3. **เข้าใช้งานระบบ:** เปิดเบราว์เซอร์ไปที่ `http://localhost:5000`

---

## 🚀 การติดตั้งบนเซิร์ฟเวอร์จริง (Production - Ubuntu)

หากเซิร์ฟเวอร์ของคุณมีการใช้งาน Apache (เช่น เว็บ WordPress) แนะนำให้รันระบบบัญชีแยกที่พอร์ต `5000` เบื้องหลัง เพื่อไม่ให้รบกวนเว็บหลัก

1. **ดึงโค้ดและเตรียมสภาพแวดล้อม:**
   ```bash
   cd /home/itech_admin/public_html/
   git clone https://github.com/patoona11/business_itech.git
   cd business_itech
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **สร้างฐานข้อมูลเริ่มต้น (รันครั้งแรกเท่านั้น):**
   ```bash
   python3 -c "from app import init_db; init_db()"
   python3 import_accounts.py
   ```

3. **สั่งรันระบบเบื้องหลังด้วย Gunicorn:**
   ```bash
   nohup gunicorn --workers 1 --threads 4 --bind 0.0.0.0:5000 app:app > gunicorn.log 2>&1 &
   ```

---

## 🔄 การอัปเดตโค้ดและจัดการ Git บน Server

เนื่องจากเซิร์ฟเวอร์ Ubuntu ไม่มีหน้าต่างเด้งให้ Login การ Push โค้ดกลับขึ้น GitHub จะต้องใช้ **Personal Access Token (PAT)** แทนรหัสผ่านปกติ

**ขั้นตอนการ Push โค้ดจาก Server:**
1. บันทึกการเปลี่ยนแปลง:
   ```bash
   git add .
   git commit -m "อัปเดตระบบ"
   ```
2. ดันโค้ดขึ้น GitHub:
   ```bash
   git push origin main
   ```
3. เมื่อระบบถามหา `Username`: ให้พิมพ์ชื่อผู้ใช้ GitHub ของคุณ
4. เมื่อระบบถามหา `Password`: **ห้ามพิมพ์รหัสผ่านปกติ** ให้ไปก๊อปปี้ `Personal Access Token` (รหัสที่ขึ้นต้นด้วย `ghp_...`) จากเว็บ GitHub มาคลิกขวาวาง แล้วกด Enter ได้เลย

**วิธีสร้าง Token (PAT):**
เข้าเว็บ GitHub -> Settings -> Developer settings -> Personal access tokens (classic) -> Generate new token -> ติ๊กช่อง `repo` -> กด Generate
