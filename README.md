# SimpleNote

## 브랜치 기록

- `feature/v2.1-core-improvements`: 기존 SimpleNote의 핵심 사용성 개선용 브랜치
  - SQLite 저장 방식을 전체 삭제/재삽입에서 개별 CRUD 방식으로 개선
  - 폴더 열림 상태 유지
  - 웹/Markdown 링크 클릭 지원
  - 검색 결과 1회 클릭으로 해당 노트 이동
  - 폴더/노트 이름 변경 시 기존 이름을 입력창에 표시
  - 이후 `main`에 merge 완료

## 변경 목록

- SQLite 저장 방식을 전체 삭제/재삽입 방식에서 개별 CRUD(INSERT / UPDATE / DELETE) 방식으로 변경
- 새 노트/폴더 생성, 이름 변경, 삭제 후에도 열려 있던 폴더 상태 유지
- 웹 주소 및 Markdown 형식 링크를 클릭 가능한 링크로 인식
- 검색 결과 창에서 결과를 한 번 클릭하면 해당 노트로 바로 이동
- 폴더/노트 이름 변경 시 기존 이름을 입력창에 미리 표시

## FastAPI + Neon 배포 구조

- SimpleNote Tkinter Client → Vercel FastAPI → Neon PostgreSQL
- 실행 시 전체 데이터 로드(15초 timeout, 실패 시 1회 자동 재시도)
- 저장 버튼 클릭 시에만 전체 데이터 1회 저장(15초 timeout)

## 로컬 테스트 방법

1. 저장소에서 `feature/fastapi-neon` 브랜치를 받습니다.
2. 가상환경을 만들고 활성화합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. 필요한 패키지를 설치합니다.

```powershell
pip install -r requirements.txt
```

4. 프로젝트 루트에 `.env` 파일을 만들고 Neon의 pooled connection string을 넣습니다.

```env
DATABASE_URL=postgresql://...-pooler....neon.tech/neondb?sslmode=require
```

5. FastAPI를 로컬에서 실행합니다.

```powershell
uvicorn backend.main:app --reload
```

6. 브라우저에서 아래 주소로 연결을 확인합니다.

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

7. SimpleNote 클라이언트를 로컬 FastAPI로 테스트하려면 실행 전에 환경변수를 지정합니다.

```powershell
$env:SIMPLENOTE_API_URL="http://127.0.0.1:8000"
python .\SimpleNote_v2.0_SQL.py
```

8. 확인 항목
   - 실행 시 `GET /sync/load`로 전체 데이터 로드 (15초 timeout, 실패 시 1회 자동 재시도)
   - 저장 버튼 클릭 시 `POST /sync/save`로 전체 데이터 저장 (15초 timeout)
   - 창의 X 버튼으로 종료할 때는 서버에 저장하지 않음
   - `/sync/load`에서 저장 결과 확인

> `.env` 파일은 GitHub에 커밋하지 않습니다.
