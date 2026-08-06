"""学习 Agent 的主 App。

继承 Kotaemon 的 App，在原 Tab 基础上插入学习特化 Tab：
    使用指南 | 快速配置 | 知识问答 | 学习路线 | 复习 | 测验 | 看板 | 资料库 | 帮助
"""

from __future__ import annotations

import logging

import gradio as gr
from decouple import config
from ktem.main import App as KotaemonApp
from theflow.settings import settings as flowsettings

logger = logging.getLogger(__name__)

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)

# 大幅增强美化 CSS
BEAUTIFY_CSS = """
<style>
:root {
    --le-primary: #4F46E5;
    --le-primary-light: #818CF8;
    --le-primary-dark: #3730A3;
    --le-bg: #F3F4F6;
    --le-card: #FFFFFF;
    --le-border: #E5E7EB;
    --le-text: #111827;
    --le-text-muted: #6B7280;
    --le-success: #10B981;
    --le-warning: #F59E0B;
    --le-danger: #EF4444;
    --le-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --le-shadow-md: 0 4px 6px -1px rgba(0,0,0,0.08), 0 2px 4px -2px rgba(0,0,0,0.05);
    --le-radius: 12px;
}

/* ===== 全局字体 ===== */
html, body, .gradio-container, .gradio-container * {
    font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", "PingFang SC", "Hiragino Sans GB", "Segoe UI", Roboto, sans-serif !important;
}

/* ===== 主容器 ===== */
.gradio-container {
    max-width: 100% !important;
    padding: 0 !important;
    background: var(--le-bg) !important;
    min-height: 100vh;
}
footer {display:none !important;}

/* ===== Tab 导航条 (顶部) ===== */
#tabs > .tab-nav {
    background: var(--le-card) !important;
    border-bottom: 1px solid var(--le-border) !important;
    padding: 0 8px !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 1000 !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
    display: flex !important;
    flex-wrap: nowrap !important;
    overflow-x: auto !important;
    scrollbar-width: thin;
}
#tabs > .tab-nav::-webkit-scrollbar {height: 4px;}
#tabs > .tab-nav::-webkit-scrollbar-thumb {background: #D1D5DB; border-radius:2px;}
#tabs > .tab-nav > button {
    font-size: 14px !important;
    font-weight: 600 !important;
    padding: 16px 16px !important;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 0 !important;
    background: transparent !important;
    color: var(--le-text-muted) !important;
    transition: all 0.2s ease !important;
    white-space: nowrap !important;
    margin: 0 !important;
}
#tabs > .tab-nav > button:hover {
    color: var(--le-primary) !important;
    background: rgba(79,70,229,0.06) !important;
}
#tabs > .tab-nav > button.selected {
    color: var(--le-primary) !important;
    border-bottom-color: var(--le-primary) !important;
    background: transparent !important;
    font-weight: 700 !important;
}

/* ===== 内容区域 ===== */
.tabitem {
    padding: 24px 32px !important;
    max-width: 1400px;
    margin: 0 auto;
}

/* ===== 卡片/区块 ===== */
.gradio-container .form,
.gradio-container .gr-block,
.gradio-container .gr-box,
.gradio-container .gradio-accordion,
.gradio-container .gr-form,
.gradio-container .wrap:not(.tab-nav):not(.gap) {
    border-radius: var(--le-radius) !important;
    border: 1px solid var(--le-border) !important;
    background: var(--le-card) !important;
    box-shadow: var(--le-shadow) !important;
}
.gradio-container .gradio-accordion {
    overflow: hidden;
}

/* ===== 输入框 ===== */
.gradio-container input[type="text"],
.gradio-container input[type="password"],
.gradio-container input[type="number"],
.gradio-container textarea,
.gradio-container select {
    border-radius: 8px !important;
    border: 1px solid var(--le-border) !important;
    font-size: 14px !important;
    transition: all 0.2s !important;
}
.gradio-container input[type="text"]:focus,
.gradio-container input[type="password"]:focus,
.gradio-container textarea:focus,
.gradio-container select:focus {
    border-color: var(--le-primary-light) !important;
    box-shadow: 0 0 0 3px rgba(79,70,229,0.12) !important;
}

/* ===== 按钮 ===== */
.gradio-container button.primary,
.gradio-container button[data-testid="submit-button"] {
    background: linear-gradient(135deg, var(--le-primary) 0%, var(--le-primary-light) 100%) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    color: white !important;
    padding: 10px 20px !important;
    box-shadow: 0 2px 8px rgba(79,70,229,0.25) !important;
    transition: all 0.2s !important;
    font-size: 14px !important;
}
.gradio-container button.primary:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(79,70,229,0.35) !important;
}
.gradio-container button.primary:active {
    transform: translateY(0) !important;
}
/* stop/危险按钮 */
.gradio-container button[variant="stop"],
.gradio-container .stop {
    background: var(--le-danger) !important;
    color: white !important;
}
/* 次按钮 */
.gradio-container button:not(.primary):not([variant="stop"]):not(.tool):not(.icon-button) {
    border-radius: 8px !important;
    border: 1px solid var(--le-border) !important;
    background: var(--le-card) !important;
    color: var(--le-text) !important;
    font-weight: 500 !important;
    padding: 10px 20px !important;
    transition: all 0.2s !important;
    font-size: 14px !important;
}
.gradio-container button:not(.primary):not([variant="stop"]):not(.tool):not(.icon-button):hover {
    border-color: var(--le-primary-light) !important;
    color: var(--le-primary) !important;
    background: rgba(79,70,229,0.04) !important;
}

/* ===== Markdown 渲染 ===== */
.gradio-container .prose, .gradio-container .md {
    font-size: 14.5px !important;
    line-height: 1.7 !important;
    color: var(--le-text) !important;
    max-width: none !important;
}
.gradio-container h1 {
    color: var(--le-text) !important;
    font-weight: 700 !important;
    font-size: 26px !important;
    margin-top: 0 !important;
    padding-bottom: 10px !important;
    border-bottom: 2px solid var(--le-primary) !important;
}
.gradio-container h2 {
    color: var(--le-text) !important;
    font-weight: 700 !important;
    font-size: 20px !important;
    border-left: 4px solid var(--le-primary) !important;
    padding-left: 12px !important;
}
.gradio-container h3 {
    color: var(--le-text) !important;
    font-weight: 600 !important;
    font-size: 17px !important;
}
.gradio-container blockquote {
    background: #EEF2FF !important;
    border-left: 4px solid var(--le-primary) !important;
    padding: 12px 16px !important;
    border-radius: 0 8px 8px 0 !important;
    color: var(--le-text) !important;
    margin: 12px 0 !important;
}
.gradio-container blockquote p {margin: 0 !important;}
.gradio-container code {
    background: #F3F4F6 !important;
    color: var(--le-primary-dark) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    font-size: 13px !important;
    font-family: "JetBrains Mono", Consolas, Monaco, monospace !important;
}
.gradio-container pre {
    border-radius: 8px !important;
    border: 1px solid var(--le-border) !important;
}
.gradio-container ul, .gradio-container ol {padding-left: 24px !important;}
.gradio-container li {margin: 4px 0 !important;}

/* ===== 表格/Dataframe ===== */
.gradio-container table, .gradio-container .gradio-dataframe {
    border-radius: 8px !important;
    overflow: hidden !important;
}
.gradio-container table thead {
    background: var(--le-primary) !important;
    color: white !important;
}
.gradio-container table th {
    color: white !important;
    font-weight: 600 !important;
}
.gradio-container table tr:nth-child(even) {
    background: #F9FAFB !important;
}

/* Project list on the learning route page: scroll instead of stretching. */
#learning-project-list,
#learning-project-list.gradio-dataframe,
#learning-project-list .gradio-dataframe,
#learning-project-list .wrap,
#learning-project-list .table-wrap,
#learning-project-list .overflow-y-auto,
#learning-project-list [data-testid="dataframe"] {
    max-height: 150px !important;
    overflow: auto !important;
}
#learning-project-list table {
    min-width: 1180px !important;
    table-layout: fixed !important;
}
#learning-project-list thead,
#learning-project-list thead tr,
#learning-project-list thead th {
    position: sticky !important;
    top: 0 !important;
    z-index: 3 !important;
}
#learning-project-list th,
#learning-project-list td {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
#learning-project-list th:nth-child(1),
#learning-project-list td:nth-child(1) {
    width: 64px !important;
}
#learning-project-list th:nth-child(2),
#learning-project-list td:nth-child(2) {
    width: 640px !important;
}
#learning-project-list th:nth-child(3),
#learning-project-list td:nth-child(3) {
    width: 220px !important;
}
#learning-project-list th:nth-child(4),
#learning-project-list td:nth-child(4) {
    width: 140px !important;
}
#learning-project-list-scroll {
    max-width: 100% !important;
    overflow: visible !important;
    padding-bottom: 8px !important;
    scrollbar-color: var(--le-primary) #E5E7EB !important;
    scrollbar-width: auto !important;
}
#learning-project-list-scroll::-webkit-scrollbar {
    height: 16px !important;
}
#learning-project-list-scroll::-webkit-scrollbar-track {
    background: #E5E7EB !important;
    border-radius: 999px !important;
}
#learning-project-list-scroll::-webkit-scrollbar-thumb {
    background: var(--le-primary) !important;
    border: 3px solid #E5E7EB !important;
    border-radius: 999px !important;
}
#learning-project-list-scroll::-webkit-scrollbar-thumb:hover {
    background: var(--le-primary-dark) !important;
}
#learning-project-list-scroll #learning-project-list,
#learning-project-list-scroll #learning-project-list > div,
#learning-project-list-scroll #learning-project-list .wrap,
#learning-project-list-scroll #learning-project-list .table-wrap {
    min-width: 1520px !important;
}
#learning-project-list .wrap,
#learning-project-list .table-wrap {
    max-height: 150px !important;
    overflow-y: scroll !important;
    scrollbar-gutter: stable !important;
}
#learning-project-list-scroll #learning-project-list th,
#learning-project-list-scroll #learning-project-list td,
#learning-project-list-scroll #learning-project-list button {
    text-overflow: clip !important;
}
#learning-project-list .wrap::-webkit-scrollbar,
#learning-project-list .table-wrap::-webkit-scrollbar {
    width: 14px !important;
    height: 14px !important;
}
#learning-project-list div[class*="table-wrap"] {
    max-height: 150px !important;
    overflow-y: scroll !important;
    overflow-x: auto !important;
}
#learning-project-list div[class*="table-wrap"]::-webkit-scrollbar {
    width: 14px !important;
    height: 14px !important;
}
#learning-project-list .wrap::-webkit-scrollbar-track,
#learning-project-list .table-wrap::-webkit-scrollbar-track,
#learning-project-list div[class*="table-wrap"]::-webkit-scrollbar-track {
    background: #E5E7EB !important;
}
#learning-project-list .wrap::-webkit-scrollbar-thumb,
#learning-project-list .table-wrap::-webkit-scrollbar-thumb,
#learning-project-list div[class*="table-wrap"]::-webkit-scrollbar-thumb {
    background: var(--le-primary) !important;
    border: 3px solid #E5E7EB !important;
    border-radius: 999px !important;
}
#learning-project-list .wrap::-webkit-scrollbar-thumb:hover,
#learning-project-list .table-wrap::-webkit-scrollbar-thumb:hover,
#learning-project-list div[class*="table-wrap"]::-webkit-scrollbar-thumb:hover {
    background: var(--le-primary-dark) !important;
}
.project-table-shell {
    max-height: 170px;
    max-width: 100%;
    overflow: auto;
    border: 1px solid var(--le-border);
    border-radius: 8px;
    background: var(--le-card);
    scrollbar-color: var(--le-primary) #E5E7EB;
    scrollbar-width: auto;
}
.project-table-shell::-webkit-scrollbar {
    width: 14px;
    height: 14px;
}
.project-table-shell::-webkit-scrollbar-track {
    background: #E5E7EB;
}
.project-table-shell::-webkit-scrollbar-thumb {
    background: var(--le-primary);
    border: 3px solid #E5E7EB;
    border-radius: 999px;
}
.project-table-shell::-webkit-scrollbar-thumb:hover {
    background: var(--le-primary-dark);
}
.project-table {
    min-width: 1450px;
    width: max-content;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 14px;
}
.project-table thead th {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--le-primary) !important;
    color: #fff !important;
}
.project-table th,
.project-table td {
    border-bottom: 1px solid var(--le-border);
    padding: 10px 12px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: left;
}
.project-table tbody tr:nth-child(even) {
    background: #F9FAFB;
}
.project-table th:nth-child(1),
.project-table td:nth-child(1) {
    width: 70px;
}
.project-table th:nth-child(2),
.project-table td:nth-child(2) {
    width: 680px;
}
.project-table th:nth-child(3),
.project-table td:nth-child(3) {
    width: 280px;
}
.project-table th:nth-child(4),
.project-table td:nth-child(4) {
    width: 150px;
}
.project-table th:nth-child(5),
.project-table td:nth-child(5) {
    width: 130px;
}
.project-table th:nth-child(6),
.project-table td:nth-child(6) {
    width: 180px;
}
.project-table-empty {
    border: 1px solid var(--le-border);
    border-radius: 8px;
    color: var(--le-text-muted);
    padding: 16px;
    background: var(--le-card);
}
.project-detail-list {
    margin-top: 12px;
    border: 1px solid var(--le-border);
    border-radius: 8px;
    background: var(--le-card);
    padding: 12px 14px;
}
.project-detail-list.muted {
    color: var(--le-text-muted);
}
.project-detail-list h4 {
    margin: 0 0 10px;
    font-size: 15px;
    color: var(--le-text);
}
.project-detail-list details {
    border-top: 1px solid var(--le-border);
    padding: 10px 0;
}
.project-detail-list details:first-of-type {
    border-top: 0;
}
.project-detail-list summary {
    cursor: pointer;
    color: var(--le-primary-dark);
    font-weight: 600;
    line-height: 1.5;
}
.project-detail-body {
    color: var(--le-text);
    margin: 8px 0 0 20px;
    line-height: 1.55;
}
.project-detail-body p {
    margin: 5px 0;
}

/* ===== 指标卡片 ===== */
.le-metric {
    display: inline-block;
    background: var(--le-card);
    border: 1px solid var(--le-border);
    border-radius: var(--le-radius);
    padding: 20px 28px;
    margin: 6px;
    text-align: center;
    box-shadow: var(--le-shadow);
    min-width: 120px;
}
.le-metric .val {
    font-size: 32px;
    font-weight: 800;
    color: var(--le-primary);
    display: block;
    line-height: 1.2;
}
.le-metric .lbl {
    font-size: 13px;
    color: var(--le-text-muted);
    margin-top: 6px;
}

/* ===== 标签页内的滚动 ===== */
.scrollable {max-height: calc(100vh - 70px) !important; overflow-y: auto !important;}

/* ===== 滚动条 ===== */
.gradio-container ::-webkit-scrollbar {width: 8px; height: 8px;}
.gradio-container ::-webkit-scrollbar-track {background: transparent;}
.gradio-container ::-webkit-scrollbar-thumb {background: #D1D5DB; border-radius: 4px;}
.gradio-container ::-webkit-scrollbar-thumb:hover {background: #9CA3AF;}

/* ===== 隐藏一些 Kotaemon 默认丑陋元素 ===== */
.gradio-container .tooltip {display: none !important;}

/* ===== 状态提示美化 ===== */
.gradio-container .prose p:first-child:empty {display: none;}
</style>
"""


class LearningApp(KotaemonApp):

    """带学习特化功能的 Kotaemon App"""

    public_events = []

    def __init__(self):
        super().__init__()
        try:
            from learning_ext.bootstrap import init_learning_ext

            init_learning_ext()
        except Exception as e:
            logger.warning(f"learning_ext 初始化延迟: {e} (将在首次使用时重试)")

    def _inject_css(self):
        try:
            gr.HTML(BEAUTIFY_CSS)
        except Exception:
            pass

    def make(self):
        markmap_js = """
        <script>
            window.markmap = {
                /** @type AutoLoaderOptions */
                autoLoader: {
                    toolbar: true, // Enable toolbar
                },
            };
        </script>
        """
        external_js = (
            "<script type='module' "
            "src='https://cdn.skypack.dev/pdfjs-viewer-element'>"
            "</script>"
            "<script type='module' "
            "src='https://cdnjs.cloudflare.com/ajax/libs/tributejs/5.1.3/tribute.min.js'>"
            f"{markmap_js}"
            "<script src='https://cdn.jsdelivr.net/npm/markmap-autoloader@0.16'></script>"
            "<script src='https://cdn.jsdelivr.net/npm/minisearch@7.1.1/dist/umd/index.min.js'></script>"
            "</script>"
            "<link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/tributejs/5.1.3/tribute.css'/>"
        )

        with gr.Blocks(
            theme=self._theme,
            css=self._css,
            title=self.app_name,
            analytics_enabled=False,
            js=self._js,
            head=external_js,
        ) as demo:
            self.app = demo
            self.settings_state.render()
            self.user_id.render()

            self.ui()

            self.declare_public_events()
            self.subscribe_public_events()
            self.register_events()
            self.on_app_created()

            demo.load(None, None, None, js=self._pdf_view_js)

        return demo

    def _build_quick_setup_tab(self, visible: bool):
        """极简模型配置页 (替换 Kotaemon 复杂的 Resources 页)"""
        from learning_ext.pages import QuickSetupPage

        with gr.Tab(
            "⚡ 模型配置",
            elem_id="quick-setup-tab",
            id="quick-setup-tab",
            visible=visible,
            elem_classes=["fill-main-area-height", "scrollable"],
        ) as self._tabs["quick-setup-tab"]:
            self.quick_setup_page = QuickSetupPage(self)
            self.quick_setup_page.on_building_ui()

    def _build_learning_tabs(self, visible: bool):
        from learning_ext.pages import (
            DashboardPage,
            PathGeneratorPage,
            QuizPage,
            ReviewPage,
            StudyWorkbenchPage,
        )

        with gr.Tab(
            "🎯 学习路线",
            elem_id="learning-path-tab",
            id="learning-path-tab",
            visible=visible,
            elem_classes=["fill-main-area-height", "scrollable"],
        ) as self._tabs["learning-path-tab"]:
            self.learning_path_page = PathGeneratorPage(self)
            self.learning_path_page.on_building_ui()

        with gr.Tab(
            "📚 学习工作台",
            elem_id="learning-workbench-tab",
            id="learning-workbench-tab",
            visible=visible,
            elem_classes=["fill-main-area-height", "scrollable"],
        ) as self._tabs["learning-workbench-tab"]:
            self.learning_workbench_page = StudyWorkbenchPage(self)
            self.learning_workbench_page.on_building_ui()

        with gr.Tab(
            "🔄 间隔复习",
            elem_id="learning-review-tab",
            id="learning-review-tab",
            visible=visible,
            elem_classes=["fill-main-area-height", "scrollable"],
        ) as self._tabs["learning-review-tab"]:
            self.learning_review_page = ReviewPage(self)
            self.learning_review_page.on_building_ui()

        with gr.Tab(
            "📝 查漏测验",
            elem_id="learning-quiz-tab",
            id="learning-quiz-tab",
            visible=visible,
            elem_classes=["fill-main-area-height", "scrollable"],
        ) as self._tabs["learning-quiz-tab"]:
            self.learning_quiz_page = QuizPage(self)
            self.learning_quiz_page.on_building_ui()

        with gr.Tab(
            "📊 学习看板",
            elem_id="learning-dashboard-tab",
            id="learning-dashboard-tab",
            visible=visible,
            elem_classes=["fill-main-area-height", "scrollable"],
        ) as self._tabs["learning-dashboard-tab"]:
            self.learning_dashboard_page = DashboardPage(self)
            self.learning_dashboard_page.on_building_ui()

    def _build_guide_tab(self, visible: bool):
        from learning_ext.guide import GUIDE_MARKDOWN

        with gr.Tab(
            "📖 使用指南",
            elem_id="learning-guide-tab",
            id="learning-guide-tab",
            visible=visible,
            elem_classes=["fill-main-area-height", "scrollable"],
        ) as self._tabs["learning-guide-tab"]:
            gr.Markdown(GUIDE_MARKDOWN)

    def _register_extra_events(self):
        for page_attr in (
            "quick_setup_page",
            "learning_path_page",
            "learning_workbench_page",
            "learning_review_page",
            "learning_quiz_page",
            "learning_dashboard_page",
        ):
            page = getattr(self, page_attr, None)
            if page is not None and hasattr(page, "on_register_events"):
                try:
                    page.on_register_events()
                except Exception as e:
                    logger.warning(f"{page_attr} 事件绑定失败: {e}")

    def ui(self):
        """重写 UI：精简 Tab 为中文 + 极简配置页替换复杂 Resources 页"""
        from ktem.pages.help import HelpPage
        from ktem.pages.setup import SetupPage
        from ktem.pages.chat import ChatPage

        KH_ENABLE_FIRST_SETUP_local = getattr(
            flowsettings, "KH_ENABLE_FIRST_SETUP", False
        )
        KH_APP_DATA_EXISTS_local = getattr(flowsettings, "KH_APP_DATA_EXISTS", True)
        if config("KH_FIRST_SETUP", default=False, cast=bool):
            KH_APP_DATA_EXISTS_local = False

        self._tabs = {}

        with gr.Tabs() as self.tabs:
            self._inject_css()

            vis = True

            # 1. 使用指南 (最先)
            self._build_guide_tab(visible=vis)
            # 2. 极简模型配置 (替换 Resources)
            self._build_quick_setup_tab(visible=vis)
            # 3. 知识问答
            with gr.Tab(
                "💬 知识问答",
                elem_id="chat-tab",
                id="chat-tab",
                visible=vis,
                elem_classes=["fill-main-area-height", "scrollable"],
            ) as self._tabs["chat-tab"]:
                self.chat_page = ChatPage(self)
            # 4-7. 学习特化
            self._build_learning_tabs(visible=vis)
            # 8. 资料库
            if len(self.index_manager.indices) == 1:
                for index in self.index_manager.indices:
                    with gr.Tab(
                        "📁 资料库",
                        elem_id="indices-tab",
                        elem_classes=[
                            "fill-main-area-height",
                            "scrollable",
                            "indices-tab",
                        ],
                        id="indices-tab",
                        visible=vis and not KH_DEMO_MODE,
                    ) as self._tabs[f"{index.id}-tab"]:
                        setattr(self, f"_index_{index.id}", index.get_index_page_ui())
            elif len(self.index_manager.indices) > 1:
                with gr.Tab(
                    "📁 资料库",
                    elem_id="indices-tab",
                    elem_classes=["fill-main-area-height", "scrollable", "indices-tab"],
                    id="indices-tab",
                    visible=vis and not KH_DEMO_MODE,
                ) as self._tabs["indices-tab"]:
                    for index in self.index_manager.indices:
                        with gr.Tab(
                            index.name, elem_id=f"{index.id}-tab"
                        ) as self._tabs[f"{index.id}-tab"]:
                            setattr(
                                self, f"_index_{index.id}", index.get_index_page_ui()
                            )
            # 9. 帮助
            with gr.Tab(
                "❓ 帮助",
                elem_id="help-tab",
                id="help-tab",
                visible=vis,
                elem_classes=["fill-main-area-height", "scrollable"],
            ) as self._tabs["help-tab"]:
                self.help_page = HelpPage(self)

            if KH_ENABLE_FIRST_SETUP_local:
                with gr.Column(visible=False) as self.setup_page_wrapper:
                    self.setup_page = SetupPage(self)

    def on_subscribe_public_events(self):
        super().on_subscribe_public_events()

    def on_register_events(self):
        super().on_register_events()
