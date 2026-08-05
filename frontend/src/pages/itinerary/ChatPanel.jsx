import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useItineraries } from "../../context/ItineraryContext";
import styles from "./itinerary.module.css";
import cx from "../../utils/cx.js";

const INITIAL_MESSAGES = [
  {
    id: 1,
    me: false,
    text: "짜잔! 고민없이 제주 2박 3일 힐링 여행 일정을 완성했어요 🎉",
    mini: "일정 확인하기 →",
  },
];

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

  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [input, setInput] = useState("");
  const bodyRef = useRef(null);

  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages]);

  const sendMsg = async () => {
    const text = input.trim();
    if (!text) return;

    // 사용자 메시지 추가
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        me: true,
        text,
      },
    ]);

    setInput("");

    try {
      // 백엔드 일정 수정
      await revise(id, text);

      // 가운데 일정 패널(ItineraryEditor)에 변경 사실을 알려 다시 불러오게 함
      onRevised?.();

      // AI 응답
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          me: false,
          text: "일정을 수정했어요 ✨",
        },
      ]);
    } catch (err) {
      console.error(err);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          me: false,
          text: "일정 수정에 실패했습니다.",
        },
      ]);
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

      <div className={styles.chatBody} ref={bodyRef}>
        {messages.map((m) => (
          <div
            key={m.id}
            className={cx(styles.msg, m.me && styles.me)}
          >
            <div className={styles.who}>
              {m.me ? "나" : "🌿"}
            </div>

            <div className={styles.bubble}>
              {m.text}

              {m.mini && (
                <>
                  <br />
                  <span className={styles.miniBtn}>
                    {m.mini}
                  </span>
                </>
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