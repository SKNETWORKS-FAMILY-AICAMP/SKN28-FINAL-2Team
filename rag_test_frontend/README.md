# RAG 임시 테스트 화면

이 폴더는 `src/rag`의 순수 Python 계약을 화면에서 시험하기 위한 임시
Streamlit 앱입니다. `backend/`나 HTTP API를 사용하지 않습니다.

## 실행

Miniforge Prompt에서 프로젝트 루트로 이동한 뒤 실행합니다.

```bat
cd /d C:\Users\Playdata\Desktop\SKN28-FINAL-2Team
rag_test_frontend\run_rag_test_ui.bat
```

또는 직접 실행할 수 있습니다.

```bat
conda activate dl_nlp_env
cd /d C:\Users\Playdata\Desktop\SKN28-FINAL-2Team
python -m streamlit run rag_test_frontend\app.py --server.port 8501
```

브라우저가 자동으로 열리지 않으면 `http://localhost:8501`에 접속합니다.

## 시험할 수 있는 흐름

1. 선택 폼으로 최초 여행 조건 전달
2. 자연어 조건을 선택 폼과 함께 전달
3. 식사 후보 부족 시 검색 반경 확대 또는 해당 식사 제외
4. `그냥 식사 장소를 빼 주세요.` 자연어 후속 요청
5. 완료 일정에서 `2일차 ○○를 다른 곳으로 교체해 주세요.` 부분 수정
6. 정규화된 조건, 검색 후보 수, 검증 결과, 전체 응답 JSON 확인

## 삭제

테스트가 끝나면 프로젝트 루트의 `rag_test_frontend` 폴더 전체를 삭제하면
됩니다. 다른 소스에는 의존 파일을 추가하지 않았습니다.
