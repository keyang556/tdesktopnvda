# Telegram 電腦版 NVDA 無障礙附加元件

## 概述

Telegram 電腦版 NVDA 無障礙附加元件適用於 Windows 版 Telegram Desktop。此附加元件提供兩個直接導覽指令，並保留 Telegram 原有的無障礙行為與控制項名稱。

## 功能

* `Alt+1` 將焦點移至聊天室清單中已選取的聊天室；沒有選取項目時，則移至第一個聊天室。
* `Alt+M` 開啟 Telegram 主選單。
* 聊天室識別使用 Telegram 穩定的 UIA 類別資訊，不使用翻譯後的控制項名稱，因此不受 Telegram 介面語言影響。
* 聊天室、訊息、按鈕及清單項目的名稱仍由 Telegram 提供；附加元件不會取代或改寫這些名稱。

## 使用方式

安裝附加元件並依提示重新啟動 NVDA 後，即可在 Telegram 主視窗使用這兩個快捷鍵，不需要另外設定。

如果 `Alt+1` 找不到聊天室清單或清單是空的，NVDA 會說明原因。如果目前的 Telegram 畫面沒有主選單，按下 `Alt+M` 時 NVDA 會提示主選單無法使用。

## 實作方式

Telegram Desktop 修補過的 Qt 無障礙提供者會透過 UIA 公開 RTTI 類別名稱。附加元件以 `Dialogs::InnerWidget` 識別聊天室清單，因此不需要比對在地化後的無障礙名稱。主選單指令則尋找 `Dialogs::Widget` 內 Telegram 原生的選單按鈕，並執行該按鈕原有的動作。

## 將 Telegram 切換為繁體中文

1. 開啟 Telegram，按下 **Main menu** 按鈕。
2. 按 `Tab` 找到 **Settings**，再按 `Enter`。
3. 按 `Tab` 找到 **Language**，再按 `Enter`。
4. 選擇 **繁體中文**。
5. 找到 **OK** 並按下，完成語言切換。

## 快速鍵

### 附加元件

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Alt+1** | 附加元件 | 將焦點移至聊天室清單 |
| **Alt+M** | 附加元件 | 開啟主選單 |

### 聊天室

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **上 / 下 / Page Up / Page Down** | Telegram Desktop | 在聊天室內導覽 |
| **Shift+捲動** | Telegram Desktop | 加速聊天室內導覽 |
| **上 / 左 / 右 / 下** | Telegram Desktop | 導覽建議的貼圖 |
| **左 / 右** | Telegram Desktop | 導覽建議的表情符號 |
| **Ctrl+Tab / Ctrl+Page Down / Alt+下** | Telegram Desktop | 移至下一個聊天室 |
| **Ctrl+Shift+Tab / Ctrl+Page Up / Alt+上** | Telegram Desktop | 移至上一個聊天室 |
| **Esc** | Telegram Desktop | 離開、返回或取消目前動作 |
| **Ctrl+O** | Telegram Desktop | 傳送檔案 |

### 資料夾

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+Shift+下** | Telegram Desktop | 移至下一個資料夾 |
| **Ctrl+Shift+上** | Telegram Desktop | 移至上一個資料夾 |
| **Ctrl+1 至 Ctrl+7** | Telegram Desktop | 直接跳至指定資料夾 |
| **Ctrl+8** | Telegram Desktop | 跳至最後一個資料夾 |

### 訊息

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+上 / Ctrl+下** | Telegram Desktop | 回覆訊息 |
| **Ctrl+下 / Esc** | Telegram Desktop | 取消回覆 |
| **上** | Telegram Desktop | 編輯最後傳送的訊息 |
| **Delete** | Telegram Desktop | 刪除目前選取的訊息 |
| **Ctrl+數字鍵台加號 / Ctrl+數字鍵台減號** | Telegram Desktop | 放大或縮小圖片／影片 |
| **Ctrl+按一下名稱** | Telegram Desktop | 從行內訊息開啟機器人個人檔案 |

### 搜尋

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+F** | Telegram Desktop | 搜尋目前聊天室 |
| **Esc** | Telegram Desktop | 離開搜尋 |
| **Ctrl+J** | Telegram Desktop | 搜尋聯絡人 |

### 快速分享面板

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **上 / 下** | Telegram Desktop | 在面板中導覽 |
| **Enter** | Telegram Desktop | 選擇聊天室 |
| **Backspace / Delete** | Telegram Desktop | 移除聊天室 |
| **Ctrl+Enter** | Telegram Desktop | 傳送訊息 |

### 跳至

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Alt+Enter** | Telegram Desktop | 跳至聊天室底部，或將聊天室清單捲至頂端 |
| **Ctrl+0** | Telegram Desktop | 開啟「我的收藏」 |
| **Ctrl+1 至 Ctrl+5** | Telegram Desktop | 沒有資料夾時，直接跳至指定的置頂聊天室 |
| **Ctrl+9** | Telegram Desktop | 開啟「封存的聊天室」 |

### 視窗

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+W / Alt+F4** | Telegram Desktop | 最小化至系統匣 |
| **Ctrl+Q** | Telegram Desktop | 結束 Telegram |
| **Ctrl+L** | Telegram Desktop | 鎖定 Telegram |
| **Ctrl+M** | Telegram Desktop | 最小化 Telegram |

### 選取的文字

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Ctrl+B** | Telegram Desktop | 粗體 |
| **Ctrl+I** | Telegram Desktop | 斜體 |
| **Ctrl+K** | Telegram Desktop | 建立連結 |
| **Ctrl+U** | Telegram Desktop | 底線 |
| **Ctrl+Shift+M** | Telegram Desktop | 等寬文字 |
| **Ctrl+Shift+N** | Telegram Desktop | 清除格式／純文字 |
| **Ctrl+Shift+P** | Telegram Desktop | 防雷格式 |
| **Ctrl+Shift+X** | Telegram Desktop | 刪除線 |
| **Ctrl+Shift+句點** | Telegram Desktop | 引言 |

### 滑鼠快捷操作

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **按兩下訊息** | Telegram Desktop | 回覆 |
| **從訊息向外拖曳** | Telegram Desktop | 選取多則訊息 |
| **將滑鼠停在時間戳記上** | Telegram Desktop | 顯示訊息資訊 |
| **將滑鼠停在投票百分比上** | Telegram Desktop | 顯示票數 |
| **將訊息拖曳至清單中的聊天室** | Telegram Desktop | 將訊息轉傳至該聊天室 |
| **返回** | Telegram Desktop | 離開「封存的聊天室」 |
| **上傳圖片後按一下預覽** | Telegram Desktop | 編輯媒體 |
| **在「傳送」按鈕按一下滑鼠右鍵** | Telegram Desktop | 無聲傳送或排程訊息 |

## 社群與支援

* **Telegram 官方頻道**：[tdesktopnvda](https://t.me/tdesktopnvda)
* **Telegram 使用者群組**：[tdesktopnvda_group](https://t.me/tdesktopnvda_group)
* **原始碼與問題追蹤**：[keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda)
* **開發者聯絡方式**：Ken Chang <lindsay714322@gmail.com>

## 支援版本

* Telegram Desktop for Windows 7.0.1 或更新版本。
* NVDA 2024.1 或更新版本。

## 從原始碼建置

在此存放庫根目錄執行：

```powershell
uv run scons
```

產生的 `.nvda-addon` 套件可透過 NVDA 附加元件商店安裝。
