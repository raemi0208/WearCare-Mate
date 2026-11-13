import React from "react";
import HealthAppLinkCard from "../components/HealthAppLinkCard";

// 기기 연동 화면: 웨어러블 기기를 직접 연결하지 않고 건강 앱(애플 건강 / 삼성 헬스 / 기타) 연동만 제공한다.
// data.timeseries 는 연동 상세의 '가져오는 데이터' 예시 값에 쓰이며, 없어도 mockData 로 동작한다.
export default function DevicesPage({ data }) {
  return (
    <div className="grid">
      <HealthAppLinkCard timeseries={data?.timeseries} />
    </div>
  );
}
