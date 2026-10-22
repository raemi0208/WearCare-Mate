# 🗄️ WearCare Mate - Database & Ingestion Architecture

"웨어케어 메이트 (WearCare Mate)" 프로젝트의 웨어러블 센서 및 활동량 데이터 파이프라인과 Amazon Timestream 시계열 데이터베이스 구축 정보를 관리하는 공간입니다.

---

## 📁 Directory Structure

```text
Database/
├── data/                             # 원본 CSV 데이터 보관 폴더 (Raw Zone)
│   ├── FitBit data.csv
│   └── wearable_tech_sleep_quality_1.csv
├── scripts/                          # Timestream 데이터 적재 파이썬 스크립트
│   ├── load_to_timestream.py         # FitBit 활동 데이터 적재 스크립트
│   └── load_sleep_to_timestream.py   # 수면 및 생체 지표 데이터 적재 스크립트
└── README.md
```
[AWS Infrastructure Specifications]
Cloud Region: us-east-2 (AWS Ohio)

Storage Layer (S3): 원본 데이터 및 전처리 데이터 적재 레이크 구조 설계

Time-Series Database: Amazon Timestream for LiveAnalytics

Database Name: wearcare_mate_db

Data Retention Policy: 마그네틱 스토어 보존 기간 31일 설정 (프로젝트 기간 내 최적화)

[Table Schemas]
fitbit_activity_table (FitBit 활동 데이터)

Timestamp: ActivityDate (날짜별 시계열 타임스탬프)

Dimensions (차원): Id (사용자 식별자)

Measures (측정값): TotalSteps, TotalDistance, Calories, SedentaryMinutes 등

wearable_sleep_table (수면 및 스트레스 데이터)

Timestamp: 측정 일시 (타임스탬프 밀리초 변환 적용)

Dimensions (차원): UserId (사용자 식별자)

Measures (측정값): Heart_Rate_Variability, Body_Temperature, Sleep_Duration_Hours, Stress_Level, Sleep_Quality_Score 등

[How to Run Ingestion Scripts]
1. 사전 요구사항 및 환경 설정
파이썬 라이브러리 설치 및 AWS IAM 사용자(db) 자격 증명(Access Key) 설정이 필요합니다.
```
Bash
pip install boto3 pandas
```

2.FitBit 활동 데이터 적재 실행
```
Bash
python scripts/load_to_timestream.py
```

3. 수면 및 생체 지표 데이터 적재 실행
```
Bash
python scripts/load_sleep_to_timestream.py
```

