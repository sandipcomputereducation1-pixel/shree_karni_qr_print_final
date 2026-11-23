# Shree Karni QR Print System v3

यह Flask आधारित Customer Upload और Print Order Management Software है।

## मुख्य सुविधाएँ
- ग्राहक Photo/PDF Upload कर सकता है (अधिकतम 25 MB)
- हर Order के लिए अलग Order ID
- Passport Photo Rotate/Zoom और 4×6 Inch शीट पर 8 फोटो
- PDF Page Range, Rotation और Crop Margin
- Admin Dashboard में Orders, Printing Status और Payment Status
- Processed File केवल Admin Download कर सकता है
- Customer Upload Page के लिए QR Code
- SQLite Database और Persistent Storage Path
- Mobile-Friendly Hindi/English Design

## Windows पर चलाने का तरीका
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:ADMIN_USER="admin"
$env:ADMIN_PASSWORD="अपना मजबूत पासवर्ड रखें"
$env:SECRET_KEY="लंबी और अलग Secret Key रखें"
python app.py
```
Browser में `http://127.0.0.1:5000` खोलें। Admin Login: `http://127.0.0.1:5000/admin/login`

## Render पर Deploy
1. सभी project files GitHub repository में upload करें।
2. Render में Blueprint बनाकर `render.yaml` चुनें।
3. Render Environment में ADMIN_USER और मजबूत ADMIN_PASSWORD सेट करें।
4. `/var/data` पर Persistent Disk attach होने की पुष्टि करें।
5. Deploy के बाद `/health`, Upload, Admin Login और QR Code test करें।

**ध्यान दें:** Render Persistent Disk paid feature है और हर plan में उपलब्ध नहीं है। Persistent storage के बिना orders और uploaded files restart/redeploy के बाद खो सकते हैं।

## सुरक्षा
- Password या SECRET_KEY को GitHub पर कभी upload न करें।
- UPI Payment अपने आप verify नहीं होता; भुगतान जाँचने के बाद Admin Paid करे।
- Software सीधे Printer को command नहीं भेजता। Admin file download करके shop PC से print करेगा।
- Customer files में निजी जानकारी हो सकती है; access सीमित रखें और पुराने files समय-समय पर हटाएँ।

## अभी उपलब्ध नहीं
- Freehand Photo Crop Editor
- Automatic UPI Payment Verification
- Direct Printer Driver Integration
- Customer के लिए अलग Live Order Tracking Login
