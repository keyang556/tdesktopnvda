# Telegram 電腦版 NVDA 輔助工具

## 概述

Telegram 電腦版 NVDA 輔助工具是一個給 NVDA 使用者使用的 Telegram Desktop 附加元件。它能改善 Telegram 電腦版在某些畫面中無法穩定朗讀的問題，讓聊天室清單、登入時的國家/地區清單，以及焦點變化更容易被聽見。

這個附加元件的功能很單純：它不會改變您的 Telegram 訊息，不會加入新的 Telegram 功能，也不會把帳號資料傳送到其他地方。它主要是在背景協助 NVDA 正常朗讀受影響的 Telegram 介面。

> [!IMPORTANT]
> 此附加元件會改善它能辨識的 Telegram 電腦版畫面。如果 Telegram 更新後介面有所改變，部分效果可能需要等待附加元件更新。

## 功能特色

* 改善 Telegram 聊天室清單的焦點朗讀。
* 改善使用電話號碼登入時，國家/地區選擇清單的朗讀。
* 保留 Telegram 原本提供的聊天室名稱與清單項目名稱。
* 在背景自動運作，不需要另外記憶新的附加元件快速鍵。

## 使用技巧與提醒

* 使用 NVDA 操作 Telegram 時，建議讓 Telegram 電腦版保持在正常、可見的視窗狀態。
* 如果更新 Telegram 後聊天室清單突然無法朗讀，請先重新啟動 Telegram 電腦版與 NVDA。
* 如果問題仍然存在，回報時請附上 Telegram 電腦版版本、NVDA 版本，以及發生問題的畫面。

## 將 Telegram 介面切換為繁體中文

1. 開啟 [繁體中文語言連結](https://t.me/setlanguage/zh-hant-beta)。
2. Telegram 開啟變更語言的確認對話框之後，按 `Tab` 找到 **Apply Language** 按鈕並按下。
3. 如果部分文字沒有立即更新，請關閉並重新開啟 Telegram Desktop。

## 此附加元件修正了什麼

某些 Telegram Desktop 6.8.x 畫面可能會讓 NVDA 無法朗讀目前焦點所在的清單列。最常見的情況是：您在聊天室清單中上下移動，但 NVDA 沒有讀出聊天室名稱。

此附加元件會避開 Telegram 在這些列上造成朗讀中斷的資訊，讓 NVDA 可以繼續讀出目前焦點項目。相同的保護也套用在電話號碼登入流程中的國家/地區選擇對話框。

## 鍵盤快速鍵

此附加元件目前沒有新增專用快速鍵。請使用 Telegram Desktop 內建快速鍵，以及 NVDA 原本的導覽方式操作。

## 社群與支援

* **官方 Telegram 頻道**：[tdesktopnvda](https://t.me/tdesktopnvda)。歡迎追蹤頻道以取得版本更新與專案消息。
* **Telegram 使用者交流群組**：[tdesktopnvda_group](https://t.me/tdesktopnvda_group)。歡迎加入群組提出建議、回報使用問題，或參與無障礙相關討論。
* **原始碼與問題追蹤**：[keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda)。如果有功能建議或發現錯誤，歡迎開 Issue；如果願意協助修正程式、改善文件或翻譯，也非常歡迎送 Pull Request。
* **聯絡開發者**：Ken Chang <lindsay714322@gmail.com>

## 支援版本

* Telegram Desktop for Windows，特別是 6.8.x 或具有相同聊天室清單朗讀問題的版本。
* NVDA 2024.1 或更新版本。

## 從原始碼建置

請在此儲存庫根目錄執行：

```powershell
uv run scons
```

產生的 `.nvda-addon` 套件可透過 NVDA 的附加元件管理員安裝。
