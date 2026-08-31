import type { Metadata } from "next";

import "./styles.css";

export const metadata: Metadata = {
  title: "学习轨迹",
  description: "Learn Everything 本地学习工作台",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
