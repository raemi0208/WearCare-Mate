import React, { useState, useRef, useEffect } from "react";
import Card from "./ui/Card";
import { sendConditionFeedback } from "../services/api";

const QUICK = [
  "오늘 무릎이 조금 뻐근해요",
  "스트레스가 너무 심해요",
  "잠을 잘 못 잤어요",
  "운동해도 될까요?",
];

export default function ConditionChat() {
  const [messages, setMessages] = useState([
    {
      role: "ai",
      text: "지금 컨디션을 알려주시면 종합 건강 데이터와 함께 분석해 맞춤 피드백을 드릴게요. (예: \"오늘 무릎이 뻐근해요\")",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    // jsdom 등 scrollIntoView 미지원 환경을 안전하게 처리
    if (typeof endRef.current?.scrollIntoView === "function") {
      endRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [messages, loading]);

  const submit = (text) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: msg }]);
    setInput("");
    setLoading(true);

    sendConditionFeedback(msg)
      .then((res) => {
        setMessages((prev) => [...prev, { role: "ai", text: res.reply }]);
      })
      .catch(() => {
        setMessages((prev) => [
          ...prev,
          { role: "ai", text: "피드백을 불러오지 못했어요. 잠시 후 다시 시도해 주세요." },
        ]);
      })
      .finally(() => setLoading(false));
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <Card
      title="AI 컨디션 체크"
      subtitle="오늘 상태를 입력하면 즉시 맞춤 피드백을 드려요"
    >
      <div className="chat">
        <div className="chat__messages">
          {messages.map((m, i) => (
            <div key={i} className={`chat__msg chat__msg--${m.role}`}>
              {m.role === "ai" && (
                <span className="chat__avatar" aria-hidden="true">
                  ✦
                </span>
              )}
              <div className="chat__bubble">{m.text}</div>
            </div>
          ))}
          {loading && (
            <div className="chat__msg chat__msg--ai">
              <span className="chat__avatar" aria-hidden="true">
                ✦
              </span>
              <div className="chat__bubble chat__bubble--typing">
                분석 중<span className="chat__dots">…</span>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="chat__quick">
          {QUICK.map((q) => (
            <button
              key={q}
              type="button"
              className="chat__quick-btn"
              onClick={() => submit(q)}
              disabled={loading}
            >
              {q}
            </button>
          ))}
        </div>

        <div className="chat__input-row">
          <input
            className="chat__input"
            type="text"
            value={input}
            placeholder="컨디션을 입력하세요"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={loading}
          />
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => submit()}
            disabled={loading || !input.trim()}
          >
            전송
          </button>
        </div>

        <p className="chat__disclaimer">
          AI 피드백은 참고용이며 의학적 진단을 대체하지 않습니다.
        </p>
      </div>
    </Card>
  );
}
