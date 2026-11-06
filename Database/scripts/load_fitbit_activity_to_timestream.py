import boto3
import pandas as pd
import time
from datetime import datetime

# 1. AWS 및 Timestream 설정 (사용 중인 리전과 데이터베이스/테이블명 확인)
REGION_NAME = "us-east-2" 
DATABASE_NAME = "wearcare_mate_db"
TABLE_NAME = "fitbit_activity_table" 

session = boto3.Session(region_name=REGION_NAME)
write_client = session.client('timestream-write')

# 2. CSV 파일 로드 (Kiro 프로젝트 내 data 폴더 경로에 맞게 수정 가능)
# 예: df = pd.read_csv('data/FitBit data.csv')
file_path = 'FitBit_data.csv' 
df = pd.read_csv(file_path)

print(f"총 {len(df)}개의 행 데이터를 [{TABLE_NAME}] 테이블에 적재를 시작합니다...")

# 3. 데이터 가공 및 Timestream 전송 (배치 처리)
records = []
for index, row in df.iterrows():
    # 타임스탬프 설정 (날짜 컬럼을 Unix Epoch 밀리초로 변환)
    try:
        dt = datetime.strptime(str(row['ActivityDate']).strip(), '%m/%d/%Y')
        timestamp_ms = str(int(dt.timestamp() * 1000))
    except Exception:
        timestamp_ms = str(int(time.time() * 1000))

    # Dimensions (차원 - 사용자 식별자 등 필터링 기준)
    dimensions = [
        {'Name': 'Id', 'Value': str(row['Id'])}
    ]

    # Measures (측정값 - 수치 데이터)
    measure_values = [
        {'Name': 'TotalSteps', 'Value': str(row['TotalSteps']), 'Type': 'BIGINT'},
        {'Name': 'TotalDistance', 'Value': str(row['TotalDistance']), 'Type': 'DOUBLE'},
        {'Name': 'Calories', 'Value': str(row['Calories']), 'Type': 'BIGINT'},
        {'Name': 'SedentaryMinutes', 'Value': str(row['SedentaryMinutes']), 'Type': 'BIGINT'}
    ]

    for mv in measure_values:
        record = {
            'Dimensions': dimensions,
            'MeasureName': mv['Name'],
            'MeasureValue': mv['Value'],
            'MeasureValueType': mv['Type'],
            'Time': timestamp_ms,
            'TimeUnit': 'MILLISECONDS'
        }
        records.append(record)

    # Timestream은 한 번에 최대 100개의 레코드씩 전송 가능
    if len(records) >= 100:
        try:
            write_client.write_records(
                DatabaseName=DATABASE_NAME,
                TableName=TABLE_NAME,
                Records=records
            )
            records = []
        except Exception as e:
            print(f"전송 에러 발생: {e}")

# 남은 레코드 처리
if records:
    try:
        write_client.write_records(
            DatabaseName=DATABASE_NAME,
            TableName=TABLE_NAME,
            Records=records
        )
    except Exception as e:
        print(f"마지막 레코드 전송 에러: {e}")

print("🎉 Timestream 데이터 적재가 완료되었습니다!")