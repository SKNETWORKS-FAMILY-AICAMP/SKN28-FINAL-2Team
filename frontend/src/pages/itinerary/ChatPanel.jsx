import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useItineraries } from "../../context/ItineraryContext";
import { getItinerary } from "../../api/itinerary";
import styles from "./itinerary.module.css";
import cx from "../../utils/cx.js";


const CHIPS = [
  "숙소도 추천해주세요",
  "근처 맛집도 알려주세요",
  "액티비티도 넣어주세요",
];

const CHIP_LABELS = [
  "숙소 추가",
  "맛집 추가",
  "액티비티 추가",
];

export default function ChatPanel({ onRevised }) {
  const { id } = useParams();
  const { revise } = useItineraries();
  const storageKey = `itinerary-chat-${id}`;
  const [messages, setMessages] = useState([]);
  const [isInitialized, setIsInitialized] = useState(false);
  const [input, setInput] = useState("");
  const [isRevising, setIsRevising] = useState(false);
  const bodyRef = useRef(null);

  

  useEffect(() => {
    const initializeMessages = async () => {
      try {
        const saved = sessionStorage.getItem(storageKey)

        if (saved) {
          const parsed = JSON.parse(saved)

          if (Array.isArray(parsed) && parsed.length > 0) {
            setMessages(parsed)
            return
          }
        }

        const itinerary = await getItinerary(id)

        setMessages([
          {
            id: crypto.randomUUID(),
            me: false,
            text: `짜잔! ${itinerary.durationLabel} 여행 일정을 완성했어요 🎉`,
            mini: "일정 확인하기 →",
          },
        ])
      } catch (err) {
        console.error("채팅 초기화 실패:", err)
      } finally {
        setIsInitialized(true)
      }
    }

    if (id) {
      initializeMessages()
    }
  }, [id, storageKey])


  useEffect(() => {
    if (!isInitialized) return

    try {
      sessionStorage.setItem(
        storageKey,
        JSON.stringify(messages)
      )
    } catch (err) {
      console.error("채팅 기록 저장 실패:", err);
    }
  }, [messages, storageKey, isInitialized]);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMsg = async () => {
    const text = input.trim();
    if (!text || isRevising) return;

    const userMessageId = crypto.randomUUID();
    const loadingMessageId = crypto.randomUUID();

    // 사용자 메시지 추가
    setMessages((prev) => [
      ...prev,
      {
        id: userMessageId,
        me: true,
        text,
      },
      {
        id: loadingMessageId,
        me: false,
        text: "생각하고 있어요...",
      },
    ]);

    setInput("");
    setIsRevising(true);

    try {
      // 백엔드 호출: 실제 일정 수정일 수도, 추천만 보여주는 것일 수도 있다.
      const result = await revise(id, text);

      if (result.mode === "recommend") {
        // 일정은 그대로 두고, 채팅창에만 후보를 보여준다.
        setMessages((prev) =>
          prev.map((message) =>
            message.id === loadingMessageId
              ? {
                  ...message,
                  text: result.message,
                  options: result.options,
                }
              : message
          )
        );
      } else if (result.mode === "no_change") {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === loadingMessageId
              ? { ...message, text: result.message }
              : message
          )
        );
      } else {
        // mode === "edit": 일정이 실제로 바뀌었으니 가운데 패널을 새로고침
        onRevised?.();

        setMessages((prev) =>
          prev.map((message) =>
            message.id === loadingMessageId
              ? { ...message, text: "일정을 수정했어요 ✨" }
              : message
          )
        );
      }
    } catch (err) {
      console.error(err);

      setMessages((prev) =>
        prev.map((message) =>
          message.id === loadingMessageId
            ? {
                ...message,
                text: "요청을 처리하지 못했습니다.",
              }
            : message
        )
      );
    } finally {
      setIsRevising(false);
    }
  }

  // 추천 카드에서 "이걸로 바꿔줘"를 눌렀을 때: 실제 편집 요청 문장을 만들어 바로 전송
  const applyOption = (optionTitle) => {
    if (isRevising) return;
    setInput(`${optionTitle}로 바꿔줘`);
  };

  return (
    <div className={styles.chatCol}>
      <div className={styles.chatHead}>
        <div className={styles.mark}>🗿</div>
        <div>
          <h2>AI 여행 코치</h2>
          <p>대화로 바로 수정해보세요</p>
        </div>
      </div>

      <div className={styles.chatBody} ref={bodyRef}>
        {messages.map((m) => (
          <div
            key={m.id}
            className={cx(styles.msg, m.me && styles.me)}
          >
            <div className={styles.who}>
              {m.me ? "나" : "🍊"}
            </div>

            <div
              className={styles.bubble}
              style={{ whiteSpace: "pre-wrap" }}
            >
              {m.text}

              {m.mini && (
                <>
                  <br />
                  <span className={styles.miniBtn}>
                    {m.mini}
                  </span>
                </>
              )}

              {m.options && m.options.length > 0 && (
                <div className={styles.suggestList}>
                  {m.options.slice(0, 3).map((opt) => (
                    <div
                      key={opt.content_id ?? opt.title}
                      className={styles.suggestCard}
                    >
                      {opt.thumbnail && (
                        <img
                          src={opt.thumbnail}
                          alt={opt.title}
                          className={styles.suggestThumb}
                        />
                      )}
                      <div className={styles.suggestBody}>
                        <h6>{opt.title}</h6>
                        {opt.summary && <p>{opt.summary}</p>}
                        {opt.address && (
                          <span className={styles.suggestAddress}>
                            {opt.address}
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        className={styles.suggestApplyBtn}
                        onClick={() => applyOption(opt.title)}
                      >
                        이걸로 바꿔줘
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.chatFoot}>
        <div className={styles.chips}>
          {CHIPS.map((text, i) => (
            <button
              key={text}
              className={styles.chip}
              onClick={() => setInput(text)}
            >
              {CHIP_LABELS[i]}
            </button>
          ))}
        </div>

        <div className={styles.inputBar}>
          <input
            type="text"
            placeholder="예: 협재해변도 가고 싶어요"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                sendMsg();
              }
            }}
          />

          <button
            className={styles.sendBtn}
            onClick={sendMsg}
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
}