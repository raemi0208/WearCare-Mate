import pandas as pd

df = pd.read_csv('FitBit_data.csv')
print(f"보전 전 전체 행 수: {len(df)}")

fixed_dates = pd.date_range(start='2016-03-12', periods=len(df), freq='D')
df['ActivityDate'] = fixed_dates.strftime('%Y-%m-%d %H:%M:%S')

df.to_csv('FitBit_data_fixed.csv', index=False)
print("보정 완료! FitBit_data_fixed.csv 파일이 생성되었습니다.")