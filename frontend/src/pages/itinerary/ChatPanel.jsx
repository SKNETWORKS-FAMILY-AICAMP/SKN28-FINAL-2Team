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
        const saved = sessionStorage.getItem(storageKey);

        if (saved) {
          const parsed = JSON.parse(saved);

          if (Array.isArray(parsed) && parsed.length > 0) {
            setMessages(parsed);
            return;
          }
        }

        const itinerary = await getItinerary(id);

        setMessages([
          {
            id: crypto.randomUUID(),
            me: false,
            text: `짜잔! ${itinerary.durationLabel} 여행 일정을 완성했어요 🎉`,
            mini: "일정 확인하기 →",
          },
        ]);
      } catch (err) {
        console.error("채팅 초기화 실패:", err);
      } finally {
        setIsInitialized(true);
      }
    };

    if (id) {
      initializeMessages();
    }
  }, [id, storageKey]);

  useEffect(() => {
    if (!isInitialized) return;

    try {
      sessionStorage.setItem(
        storageKey,
        JSON.stringify(messages)
      );
    } catch (err) {
      console.error("채팅 기록 저장 실패:", err);
    }
  }, [messages, storageKey, isInitialized]);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop =
        bodyRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMsg = async () => {
    const text = input.trim();

    if (!text || isRevising) return;

    const userMessageId = crypto.randomUUID();
    const loadingMessageId = crypto.randomUUID();

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
        text: "일정을 수정하고 있어요...",
      },
    ]);

    setInput("");
    setIsRevising(true);

    try {
      await revise(id, text);

      // ItineraryEditor와 MapPanel을 다시 조회하게 한다.
      onRevised?.();

      setMessages((prev) =>
        prev.map((message) =>
          message.id === loadingMessageId
            ? {
                ...message,
                text: "일정을 수정했어요 ✨",
              }
            : message
        )
      );
    } catch (err) {
      console.error(err);

      setMessages((prev) =>
        prev.map((message) =>
          message.id === loadingMessageId
            ? {
                ...message,
                text: "일정 수정에 실패했습니다.",
              }
            : message
        )
      );
    } finally {
      setIsRevising(false);
    }
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

      <div
        className={styles.chatBody}
        ref={bodyRef}
      >
        {messages.map((message) => (
          <div
            key={message.id}
            className={cx(
              styles.msg,
              message.me && styles.me
            )}
          >
            <div className={styles.who}>
              {message.me ? "나" : "🌿"}
            </div>

            <div
              className={styles.bubble}
              style={{ whiteSpace: "pre-line" }}
            >
              {message.text}

              {message.mini && (
                <>
                  <br />

                  <span className={styles.miniBtn}>
                    {message.mini}
                  </span>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className={styles.chatFoot}>
        <div className={styles.chips}>
          {CHIPS.map((text, index) => (
            <button
              key={text}
              className={styles.chip}
              onClick={() => setInput(text)}
            >
              {CHIP_LABELS[index]}
            </button>
          ))}
        </div>

        <div className={styles.inputBar}>
          <input
            type="text"
            placeholder="예: 협재해변도 가고 싶어요"
            value={input}
            onChange={(event) =>
              setInput(event.target.value)
            }
            onKeyDown={(event) => {
              if (event.key === "Enter") {
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