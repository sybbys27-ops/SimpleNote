# SimpleNote

## 변경 목록

- SQLite 저장 방식을 전체 삭제/재삽입 방식에서 개별 CRUD(INSERT / UPDATE / DELETE) 방식으로 변경
- 새 노트/폴더 생성, 이름 변경, 삭제 후에도 열려 있던 폴더 상태 유지
- 웹 주소 및 Markdown 형식 링크를 클릭 가능한 링크로 인식
- 검색 결과 창에서 결과를 한 번 클릭하면 해당 노트로 바로 이동
- 폴더/노트 이름 변경 시 기존 이름을 입력창에 미리 표시

## FastAPI + Neon 배포 구조

- SimpleNote Tkinter Client → Vercel FastAPI → Neon PostgreSQL
- 실행 시 전체 데이터 1회 로드
- 저장 버튼 및 창 종료 시 전체 데이터 1회 저장
