# WearCare Mate Backend

AWS Lambda와 API Gateway 기반 백엔드 서비스

## 담당 기능
- REST API 개발
- AI/ML 서비스 연동
- Amazon SNS 알림
- 오류 처리 및 AWS 인프라 관리

## 개발 상태
- 초기 프로젝트 구조 생성
- `GET /health` 헬스체크 엔드포인트 구현 (표준 라이브러리만 사용)

## 폴더 구조
```text
backend/
├── src/
│   ├── __init__.py          # src 를 파이썬 패키지로 인식시키는 파일
│   └── lambda_function.py   # Lambda 핸들러(진입점) 구현
├── tests/
│   └── test_lambda.py       # unittest 기반 단위 테스트
├── requirements.txt         # 외부 의존성 목록(현재 없음)
└── README.md
```

## API 엔드포인트
| 메서드 | 경로      | 설명         | 응답(200)                                              |
| ------ | --------- | ------------ | ------------------------------------------------------ |
| GET    | `/health` | 헬스체크     | `{"status": "ok", "service": "WearCare Mate Backend"}` |

- 지원하지 않는 경로/메서드: `404`
- 잘못된 이벤트 형식: `400`
- 이벤트 기준: API Gateway HTTP API, payload format 2.0

## 로컬 테스트 실행 방법

아래 명령은 모두 `backend/` 폴더에서 실행합니다.

### 1) 가상환경 활성화 (Windows / cmd)
```bat
.venv\Scripts\activate
```

### 2) 단위 테스트 실행
```bat
python -m unittest discover -s tests -v
```

가상환경을 활성화하지 않고 바로 실행하려면(권장, 경로 문제 예방):
```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- 외부 패키지가 필요 없으므로 `pip install` 없이 바로 실행됩니다.
- Python 3.13 기준으로 6개 테스트 통과를 확인했습니다.
- 반드시 `backend/` 폴더에서 실행해야 `tests` 패키지를 찾을 수 있습니다.

### (참고) 특정 테스트 파일만 실행
```bat
python -m unittest tests.test_lambda -v
```
