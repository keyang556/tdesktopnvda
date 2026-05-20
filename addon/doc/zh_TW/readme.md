# Telegram 電腦版無障礙支援

Telegram 電腦版無障礙支援是為 NVDA 使用者設計的 Telegram Desktop 附加元件。它改善 Telegram 電腦版在螢幕閱讀器下的朗讀穩定性，讓聊天室清單、焦點變化與相關狀態更容易被理解。

## 已修正問題

Telegram Desktop 6.8.x 會將聊天室清單暴露為 UIA 清單項目，但在 NVDA 準備焦點朗讀時，`SelectionItemPattern.currentSelectionContainer` 可能引發 COM 錯誤。發生此狀況時，NVDA 會中止焦點事件，導致聊天室列無法被朗讀。

此附加元件會針對受影響的清單列加入 Telegram 專用的 appModule overlay。它保留 Telegram 原有的可存取列名稱，並讓這些列不回傳選取容器，避免觸發會阻斷朗讀的 UIA 查詢。相同的保護也套用到 Telegram Desktop `CountrySelectBox` 所引入的電話號碼國家/地區選擇對話框。

## 語言

- 英文：`README.md`
- 繁體中文：`addon/doc/zh_TW/readme.md`
- 簡體中文：`addon/doc/zh_CN/readme.md`

附加元件的 manifest 以英文作為預設語言，並透過 `addon/locale/zh_TW/LC_MESSAGES/nvda.po` 提供繁體中文中繼資料。

## 建置

請在此儲存庫根目錄執行：

```powershell
uv run scons
```

產生的 `.nvda-addon` 套件可透過 NVDA 的附加元件管理員安裝。

## 作者

Ken Chang <lindsay714322@gmail.com>
