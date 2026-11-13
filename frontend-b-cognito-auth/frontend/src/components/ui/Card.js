import React from "react";

// 재사용 카드 컨테이너
export default function Card({ title, subtitle, action, className = "", children }) {
  return (
    <section className={`card ${className}`.trim()}>
      {(title || action) && (
        <header className="card__header">
          <div>
            {title && <h3 className="card__title">{title}</h3>}
            {subtitle && <p className="card__subtitle">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="card__body">{children}</div>
    </section>
  );
}
