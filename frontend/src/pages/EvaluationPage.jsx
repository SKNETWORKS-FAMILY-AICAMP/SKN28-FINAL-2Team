import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  evaluationDownloadUrl,
  getBackendHealth,
  getEvaluationJob,
  getEvaluationReport,
  listEvaluationCases,
  runEvaluation,
} from '../api/client.js'
import styles from './evaluation/evaluation.module.css'

const TERMINAL_STATUSES = new Set(['completed', 'failed'])

function pct(value) {
  return `${Math.round(Number(value || 0) * 100)}%`
}

function score(value) {
  return Number(value || 0).toFixed(3)
}

function warningList(artifact, caseId) {
  const raw = (artifact?.raw_results || []).find((item) => item.case_id === caseId)
  return raw?.result?.validation?.warnings || []
}

export default function EvaluationPage() {
  const [health, setHealth] = useState(null)
  const [cases, setCases] = useState([])
  const [selected, setSelected] = useState(new Set())
  const [repeat, setRepeat] = useState(1)
  const [includeResults, setIncludeResults] = useState(true)
  const [llmJudge, setLlmJudge] = useState(false)
  const [job, setJob] = useState(null)
  const [artifact, setArtifact] = useState(null)
  const [activeCaseId, setActiveCaseId] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    Promise.all([getBackendHealth(), listEvaluationCases()])
      .then(([healthPayload, casePayload]) => {
        if (!alive) return
        setHealth(healthPayload)
        setCases(casePayload.cases || [])
        const preferred = (casePayload.cases || []).find((item) => item.id === 'rag_halla_arboretum')
        if (preferred) setSelected(new Set([preferred.id]))
      })
      .catch((err) => alive && setError(err.message))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => {
    if (!job || TERMINAL_STATUSES.has(job.status)) return undefined
    const timer = window.setInterval(async () => {
      try {
        const next = await getEvaluationJob(job.job_id)
        setJob(next)
        if (TERMINAL_STATUSES.has(next.status)) {
          window.clearInterval(timer)
          if (next.status === 'completed' && next.report_available) {
            const report = await getEvaluationReport(next.job_id)
            setArtifact(report)
            setActiveCaseId(report.report?.cases?.[0]?.case_id || null)
          }
        }
      } catch (err) {
        setError(err.message)
        window.clearInterval(timer)
      }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [job])

  const report = artifact?.report
  const activeCase = useMemo(
    () => report?.cases?.find((item) => item.case_id === activeCaseId),
    [report, activeCaseId],
  )
  const warnings = warningList(artifact, activeCaseId)

  const toggleCase = (caseId) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(caseId)) next.delete(caseId)
      else next.add(caseId)
      return next
    })
  }

  const startEvaluation = async () => {
    if (!selected.size) {
      setError('평가할 케이스를 한 개 이상 선택하세요.')
      return
    }
    setError('')
    setArtifact(null)
    setActiveCaseId(null)
    try {
      const created = await runEvaluation({
        case_ids: [...selected],
        repeat: Number(repeat),
        include_results: includeResults,
        llm_judge: llmJudge,
      })
      setJob(created)
    } catch (err) {
      setError(err.message)
    }
  }

  const ragReady = health?.rag?.openai_api_key_configured && health?.rag?.mysql_configured && health?.rag?.chroma_index_ready

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link to="/" className={styles.brand}>🌿 탐나플랜</Link>
        <nav>
          <Link to="/chat">여행 일정 만들기</Link>
          <span className={styles.current}>평가 대시보드</span>
        </nav>
      </header>

      <main className={styles.main}>
        <section className={styles.hero}>
          <div>
            <span className={styles.eyebrow}>Developer Quality Console</span>
            <h1>feature/backend RAG 검색 품질을 직접 평가합니다.</h1>
            <p>현재 프로젝트의 feature/backend PlaceSearchService를 FastAPI가 실행하고, 검색 정확도·필터 준수·MySQL 근거성·응답 시간을 표시합니다.</p>
          </div>
          <div className={`${styles.systemCard} ${ragReady ? styles.ok : styles.bad}`}>
            <strong>{ragReady ? '연동 준비 완료' : '환경 점검 필요'}</strong>
            <span>OpenAI {health?.rag?.openai_api_key_configured ? '✓' : '✕'}</span>
            <span>MySQL {health?.rag?.mysql_configured ? '✓' : '✕'}</span>
            <span>ChromaDB {health?.rag?.chroma_index_ready ? '✓' : '✕'}</span>
          </div>
        </section>

        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.grid}>
          <section className={styles.panel}>
            <div className={styles.panelTitle}>
              <div>
                <span>01</span>
                <h2>평가 케이스</h2>
              </div>
              <button className={styles.textButton} onClick={() => setSelected(new Set(cases.map((item) => item.id)))}>전체 선택</button>
            </div>

            {loading ? (
              <p className={styles.muted}>백엔드에서 골든셋을 읽는 중입니다.</p>
            ) : (
              <div className={styles.caseList}>
                {cases.map((item) => (
                  <label className={`${styles.caseItem} ${selected.has(item.id) ? styles.selected : ''}`} key={item.id}>
                    <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleCase(item.id)} />
                    <div>
                      <strong>{item.id}</strong>
                      <span>{item.stage}</span>
                      <p>{item.message || `${item.selected_options?.duration_days || '-'}일 선택형 RAG 시나리오`}</p>
                    </div>
                  </label>
                ))}
              </div>
            )}

            <div className={styles.options}>
              <label>
                반복 횟수
                <input type="number" min="1" max="10" value={repeat} onChange={(event) => setRepeat(event.target.value)} />
              </label>
              <label className={styles.checkOption}>
                <input type="checkbox" checked={includeResults} onChange={(event) => setIncludeResults(event.target.checked)} />
                원본 RAG 결과 포함
              </label>
              <label className={styles.checkOption} title="feature/backend 검색 평가기는 결정론적 지표만 사용합니다.">
                <input type="checkbox" checked={false} disabled />
                LLM Judge 미사용
              </label>
            </div>

            <button className={styles.runButton} disabled={job && !TERMINAL_STATUSES.has(job.status)} onClick={startEvaluation}>
              {job && !TERMINAL_STATUSES.has(job.status) ? '평가 실행 중…' : `${selected.size}개 케이스 평가 실행`}
            </button>
          </section>

          <section className={styles.panel}>
            <div className={styles.panelTitle}>
              <div>
                <span>02</span>
                <h2>실행 상태</h2>
              </div>
              {job && <b className={styles.statusBadge}>{job.status}</b>}
            </div>

            {!job ? (
              <div className={styles.empty}>왼쪽에서 케이스를 선택하고 평가를 실행하세요.</div>
            ) : (
              <>
                <div className={styles.progressInfo}>
                  <strong>{job.completed_cases} / {job.total_cases}</strong>
                  <span>{pct(job.progress)}</span>
                </div>
                <div className={styles.progressTrack}><div style={{ width: pct(job.progress) }} /></div>
                {job.error && <div className={styles.error}>{job.error}</div>}
                <pre className={styles.log}>{(job.logs || []).slice(-18).join('\n') || '평가 프로세스를 준비하고 있습니다…'}</pre>
              </>
            )}
          </section>
        </div>

        {report && (
          <>
            <section className={styles.summaryCards}>
              <article className={report.passed ? styles.passCard : styles.failCard}>
                <span>전체 결과</span>
                <strong>{report.passed ? 'PASS' : 'FAIL'}</strong>
              </article>
              <article><span>평균 점수</span><strong>{score(report.average_score)}</strong></article>
              <article><span>통과율</span><strong>{pct(report.pass_rate)}</strong></article>
              <article><span>케이스 수</span><strong>{report.case_count}</strong></article>
            </section>

            <div className={styles.resultGrid}>
              <section className={styles.panel}>
                <div className={styles.panelTitle}><div><span>03</span><h2>지표 평균</h2></div></div>
                <div className={styles.metricList}>
                  {Object.entries(report.metric_averages || {}).map(([name, value]) => (
                    <div key={name}>
                      <code>{name}</code>
                      <div className={styles.metricBar}><i style={{ width: pct(value) }} /></div>
                      <b>{score(value)}</b>
                    </div>
                  ))}
                </div>
              </section>

              <section className={styles.panel}>
                <div className={styles.panelTitle}><div><span>04</span><h2>케이스 결과</h2></div></div>
                <div className={styles.resultCases}>
                  {(report.cases || []).map((item) => (
                    <button className={activeCaseId === item.case_id ? styles.activeCase : ''} onClick={() => setActiveCaseId(item.case_id)} key={item.case_id}>
                      <span className={item.passed ? styles.passDot : styles.failDot}>{item.passed ? 'PASS' : 'FAIL'}</span>
                      <strong>{item.case_id}</strong>
                      <b>{score(item.score)}</b>
                    </button>
                  ))}
                </div>
                <div className={styles.downloads}>
                  <a href={evaluationDownloadUrl(job.job_id, 'json')}>JSON 보고서</a>
                  <a href={evaluationDownloadUrl(job.job_id, 'md')}>Markdown 보고서</a>
                </div>
              </section>
            </div>

            {activeCase && (
              <section className={styles.panel}>
                <div className={styles.panelTitle}>
                  <div><span>05</span><h2>{activeCase.case_id} 상세</h2></div>
                  <b className={activeCase.passed ? styles.passText : styles.failText}>{activeCase.passed ? 'PASS' : 'FAIL'}</b>
                </div>
                <div className={styles.detailGrid}>
                  <div>
                    <h3>개별 지표</h3>
                    <table>
                      <thead><tr><th>지표</th><th>점수</th><th>게이트</th><th>결과</th></tr></thead>
                      <tbody>
                        {(activeCase.metrics || []).map((metric) => (
                          <tr key={metric.name}>
                            <td><code>{metric.name}</code></td>
                            <td>{score(metric.value)}</td>
                            <td>{metric.gate ? '필수' : '-'}</td>
                            <td className={metric.passed ? styles.passText : styles.failText}>{metric.passed ? 'PASS' : 'FAIL'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div>
                    <h3>검증 경고 ({warnings.length})</h3>
                    {warnings.length ? (
                      <div className={styles.warningList}>
                        {warnings.map((warning, index) => (
                          <article key={`${warning.code}-${index}`}>
                            <strong>{warning.code || `warning-${index + 1}`}</strong>
                            <p>{warning.message || String(warning)}</p>
                            {(warning.day || warning.content_id) && <span>Day {warning.day || '-'} · content_id {warning.content_id || '-'}</span>}
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className={styles.muted}>{includeResults ? '검증 경고가 없습니다.' : '원본 결과 포함 옵션을 켜야 경고를 표시할 수 있습니다.'}</p>
                    )}
                  </div>
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  )
}
