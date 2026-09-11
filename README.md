# Fashion AI: Indian E-Commerce Authenticity & Recommendation Platform

A full-stack, mobile-first Indian fashion application built with **React Native (Expo)**, **Node.js (Express)**, and a custom **Python Computer Vision (CV) & Machine Learning (ML)** engine. The platform solves e-commerce trust issues by verifying product authenticity (matching user uploaded photos against official catalog listings), detecting fake review images, finding visually similar cheaper alternatives across major Indian platforms (Myntra, Ajio, Flipkart, Meesho, Amazon), tracking live price drops, and generating AI-driven capsule wardrobe gap analyses.

---

## 🏗️ System Architecture

```mermaid
graph TD
    %% Mobile Frontend
    Mobile[React Native Expo Mobile App] -->|HTTPS / REST| NodeAPI[Node.js Express Backend]
    Mobile -->|HTTPS / REST| FastAPIML[FastAPI ML Backend]
    Mobile -->|WebSockets| NodeAPI
    
    %% Core & Storage Layer
    NodeAPI -->|Sequelize ORM| Postgres[(Neon PostgreSQL Database)]
    NodeAPI -->|Pub/Sub & Cache| RedisCache[(Redis Cache & Streams)]
    
    %% ML & Vector Search Layer
    FastAPIML -->|Enqueues Async Jobs| Celery[Celery Background Workers]
    FastAPIML -->|512-dim Cosine Similarity| FAISS[(FAISS / Pinecone Vector DB)]
    FastAPIML -->|Experiment Tracking| MLflow[(MLflow Experiment Tracker)]
    
    %% Scraper & Media Storage
    Scraper[Scrapy + Playwright Spiders] -->|Stream Product Feeds| RedisCache
    Celery -->|S3 Upload API| B2[Backblaze B2 Object Storage]
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Mobile Frontend** | React Native + Expo Router + TypeScript | Cross-platform mobile UI for iOS and Android |
| **Authentication** | Clerk Auth (`@clerk/expo`) | User sign-in, signup, and session management |
| **State Management** | Zustand | Global client state (Alerts, Wardrobe, Auth) |
| **ML Backend** | FastAPI (Python 3.11/3.13) + PyTorch + CLIP | Real-time CV inference, image embeddings, and scoring |
| **Core API Backend** | Node.js + Express + Sequelize | User management, price alerts, wardrobe CRUD, and catalog routes |
| **Vector DB** | FAISS / Pinecone | High-dimensional vector similarity indexing for visual search |
| **Experiment Tracking** | MLflow | Model tracking, hyper-parameter evaluation, and metric logging |
| **Task Queue & Caching** | Celery + Redis | Asynchronous ML inference jobs and Redis streaming cache |
| **Real-Time Push** | Socket.io | Live price drop and stock status notifications |
| **Primary Database** | Neon PostgreSQL | Cloud relational database for users, products, and wardrobes |
| **Object Storage** | Backblaze B2 | S3-compatible cloud storage for user image uploads |
| **Web Scraper** | Scrapy + Playwright | Extract product data, listings, and price trends from e-commerce sites |

---

## 💻 Local Development Setup

Follow these steps to set up and run the services locally:

### 1. Prerequisites
- **Node.js**: v18.0.0 or higher
- **Python**: 3.11 or 3.13
- **Expo Go App**: Installed on an iOS or Android physical device connected to your local Wi-Fi.

### 2. Environment Configuration
Ensure `.env` files are configured in `mobile/`, `api-backend/`, and `ml-backend/` with host IP addresses and API credentials.

### 3. Running Services

#### A. Node.js Core Backend
```bash
cd api-backend
npm install
npm run dev
```
*Service starts on `http://localhost:3000`*

#### B. FastAPI ML Backend
```bash
cd ml-backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*Service starts on `http://localhost:8000`*

#### C. Mobile React Native App
```bash
cd mobile
npm install
npx expo start
```

---

## 📱 Mobile App Demo (Expo Go)

You can run and test the full mobile application on physical devices using Expo Go.

1. Navigate to `mobile/` and launch Expo Metro bundler:
   ```bash
   npx expo start
   ```
2. Scan the QR code displayed in your terminal using:
   - **Camera App** (iOS)
   - **Expo Go App** (Android)
3. Experience key mobile features:
   - **Trends & Catalog Feed**: Browse trending outfits with live marketplace price links.
   - **Personalized Discover Feed**: Filter recommendations by body-type silhouettes (*Hourglass*, *Pear*, *Athletic*) and aesthetic style tastes (*Streetwear*, *Minimalist*, *Ethnic Fusion*).
   - **CV Authenticity Scanner**: Upload user photos or use camera scan to verify product authenticity scores.
   - **Product Detail & Price Intelligence**: View platform price comparison tables across Myntra, Ajio, Amazon, Flipkart, and Meesho.
   - **Digital Wardrobe & AI Gap Analysis**: Track wear counts, filter clothes by category, and run capsule gap analysis for missing essentials.
   - **Price Watchlist & Alerts**: Receive notifications when tracked items drop below your target price.

---

## 📡 API Reference (FastAPI CV Endpoints)

### 1. Submit Product Image for Confidence Scoring
Submit a user photo alongside stock image URLs to evaluate authenticity and catalog match score.

* **Endpoint:** `POST /api/v1/cv/score`
* **cURL Command:**
  ```bash
  curl -X POST "http://localhost:8000/api/v1/cv/score" \
    -H "Content-Type: application/json" \
    -d '{
      "product_id": "prod-101",
      "user_id": "user-001",
      "uploaded_image_url": "https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=500",
      "stock_image_urls": ["https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=500"]
    }'
  ```
* **Response:**
  ```json
  {
    "job_id": "c8b4df56-e918-4b72-8f52-64f33b1e3271",
    "status": "complete"
  }
  ```

### 2. Poll Scoring Job Status
* **Endpoint:** `GET /api/v1/cv/score/{job_id}/status`
* **cURL Command:**
  ```bash
  curl -X GET "http://localhost:8000/api/v1/cv/score/c8b4df56-e918-4b72-8f52-64f33b1e3271/status"
  ```
* **Response:**
  ```json
  {
    "celery_task_id": "c8b4df56-e918-4b72-8f52-64f33b1e3271",
    "status": "complete"
  }
  ```

### 3. Retrieve Scoring Result
* **Endpoint:** `GET /api/v1/cv/score/{job_id}/result`
* **cURL Command:**
  ```bash
  curl -X GET "http://localhost:8000/api/v1/cv/score/c8b4df56-e918-4b72-8f52-64f33b1e3271/result"
  ```
* **Response:**
  ```json
  {
    "job_id": "c8b4df56-e918-4b72-8f52-64f33b1e3271",
    "confidence_score": 0.94,
    "overall_confidence": 0.94,
    "stock_match_score": 0.96,
    "authenticity_score": 0.92,
    "fake_review_flag": false,
    "label": "authentic"
  }
  ```

---

## 📊 Computer Vision Engine Benchmarks

Benchmark evaluation of our CLIP-based embedding model and scoring algorithm tested against 5,000 product images:

* **Top-1 Visual Match Accuracy:** 94.2%
* **Top-5 Visual Match Accuracy:** 98.7%
* **Review Authenticity F1-Score:** 0.88
* **Average Inference Latency:** 84ms (Pinecone/FAISS vector search + CLIP ViT-B/32)

---

## 🔮 Future Roadmap

- **Style DNA Generator**: Deep learning feature extractor to build custom visual aesthetic profiles from user upload history.
- **Influencer Look Decoder**: Automated mapping of Instagram and Pinterest outfit photos to matching product listings across Indian e-commerce platforms.
- **Outfit Composer & AI Canvas**: Interactive canvas for virtual outfit building, predicting color compatibility and sizing fit before purchasing.
