
# 🍽️ Score My Food

A mobile + backend app to scan foods and get a **health score** with positives, negatives, and additives info.

* **Backend** → Django REST Framework
* **Frontend** → React Native (Expo)

---

## ✨ Features

* 📦 **Barcode scan** → Get product info & health score from OpenFoodFacts
* 📝 **Ingredients OCR scan** → Take photo of label, extract ingredients, analyze
* 🔍 **Search by category/keyword** → Browse snacks, cereals, yogurts, etc.
* 🛒 **Grocery List Builder** → Enter items + budget → get healthiest basket
* 👤 **Profile page** → Demo user, editable info, streaks & badges

---

## 🚀 Setup

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/score-my-food.git
cd score-my-food
```

---

### 2. Backend (Django)

```bash
cd backend
python -m venv venv          # create virtual env
venv\Scripts\activate        # Windows
# or source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

✅ Backend runs on port **8000**.
Check: open in browser → `http://<your-ip>:8000/api/ping`

---

### 3. Frontend (React Native + Expo)

```bash
cd app
npm install
npm start
```

Scan the QR code with the **Expo Go** app on your phone.

---

## 🌐 Configure API URL

1. Find your **IPv4 address**:

   * Windows → `ipconfig`
   * Mac/Linux → `ifconfig` or `ip a`
     Example: `192.168.1.42`

2. Open `app/lib/api.js` and set:

```js
export const API = axios.create({
  baseURL: "http://192.168.1.42:8000",  // replace with YOUR IPv4
  timeout: 10000,
});
```

⚠️ Phone and laptop must be on the **same Wi-Fi**.

---

## ✅ Quick Test

* Visit `http://<your-ip>:8000/api/ping` → should return

  ```json
  { "app": "score-my-food", "ok": true }
  ```

* In app, try:

  * **Scan → Barcode**
  * **Scan → Ingredients (OCR)**
  * **Pantry → Grocery List Builder**

---
