# Telegram 電腦版 NVDA 無障礙附加元件

* 作者：[Ken Chang](https://t.me/Keyang556)
* [Telegram 頻道](https://t.me/tdesktopnvda)
* [Telegram 使用者群組](https://t.me/tdesktopnvda_group)

## 概述

Telegram 電腦版 NVDA 無障礙附加元件適用於 Windows 版 Telegram Desktop。此附加元件提供直接導覽與通話指令，並保留 Telegram 原有的無障礙行為與控制項名稱。

## 功能

* `Alt+1` 將焦點移至聊天室清單中已選取的聊天室；沒有選取項目時，則移至第一個聊天室。
* `Alt+M` 開啟 Telegram 主選單。
* `Alt+Y`、`Alt+N`、`Alt+A` 與 `Alt+V` 分別用來接聽通話、拒接或掛斷、開關麥克風，以及開關攝影機。每個指令都會以 Telegram 本身的用語報出所執行的動作，因此會跟隨 Telegram 的介面語言。
* 所有指令都會列在 NVDA 的「輸入手勢」對話方塊中，歸類於「Telegram Desktop Accessibility」，因此可以自行變更或移除預設快速鍵。在 Telegram 以外的程式，按鍵會原封不動地傳給該程式。
* 主選單的結構性控制項（例如個人資料與帳號）、未命名的輸入列控制項，以及頂端列的建議項目，都會取得可用的無障礙標籤。Telegram 已提供的真實名稱一律保留。
* 當 UnigramPlus 或其他附加元件搶到 Telegram 共用的 app module 名額時，會由前景偵測的備援機制繼續提供這些快速鍵與標籤，且不會在 Telegram 以外綁定按鍵。
* 聊天室與通話控制項的識別使用 Telegram 穩定的 UIA 類別資訊，不使用翻譯後的控制項名稱，因此不受 Telegram 介面語言影響。
* 只公開 Telegram 內部 C++ 類別路徑的控制項不再朗讀該路徑；Telegram 提供的其他名稱不會被取代。

## 使用方式

安裝附加元件並依提示重新啟動 NVDA 後，即可在 Telegram 主視窗使用這些快速鍵，不需要另外設定。

如果 `Alt+1` 找不到聊天室清單或清單是空的，NVDA 會說明原因。如果目前的 Telegram 畫面沒有主選單，按下 `Alt+M` 時 NVDA 會提示主選單無法使用。找不到對應的控制項時，通話指令會提示沒有來電或目前未在通話中。通話會在獨立視窗中進行，因此即使 Telegram 主視窗在前景，通話指令仍然可用。

若要改用其他按鍵，請開啟「NVDA 功能表」>「偏好設定」>「輸入手勢」，展開「Telegram Desktop Accessibility」分類，再為任一指令新增或移除手勢。

## 將 Telegram 切換為繁體中文

1. 開啟 Telegram，按下 **Main menu** 按鈕。
2. 按 `Tab` 找到 **Settings**，再按 `Enter`。
3. 按 `Tab` 找到 **Language**，再按 `Enter`。
4. 選擇 **繁體中文**。
5. 找到 **OK** 並按下，完成語言切換。

## 快速鍵

> 「提供者」欄中，`附加元件` 表示由本附加元件提供的快速鍵，`Telegram Desktop` 表示 Telegram Desktop 內建的快速鍵。
>
> **提示：**附加元件的快速鍵可從「NVDA 功能表」>「偏好設定」>「輸入手勢」自行變更。

### 聊天室

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Alt+1** | 附加元件 | 將焦點移至聊天室清單 |
| **上 / 下 / Page Up / Page Down** | Telegram Desktop | 在聊天室內導覽 |
| **Shift+捲動** | Telegram Desktop | 加速聊天室內導覽 |
| **上 / 左 / 右 / 下** | Telegram Desktop | 導覽建議的貼圖 |
| **左 / 右** | Telegram Desktop | 導覽建議的表情符號 |
| **Ctrl+Tab / Ctrl+Page Down / Alt+下** | Telegram Desktop | 移至下一個聊天室 |
| **Ctrl+Shift+Tab / Ctrl+Page Up / Alt+上** | Telegram Desktop | 移至上一個聊天室 |
| **Esc** | Telegram Desktop | 離開、返回或取消目前動作 |
| **Ctrl+O** | Telegram Desktop | 傳送檔案 |

### 通話

| 快速鍵 | 提供者 | 功能 |
|---|---|---|
| **Alt+Y** | 附加元件 | 接聽來電 |
| **Alt+N** | 附加元件 | 拒接來電，或掛斷進行中的通話 |
| **Alt+A** | 附加元件 | 通話中開啟或關閉麥克風 |
| **Alt+V** | 附加元件 | 通話中開啟或關閉攝影機 |

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
| **Alt+M** | 附加元件 | 開啟主選單 |
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

## 實作方式

Telegram Desktop 修補過的 Qt 無障礙提供者會透過 UIA 公開 RTTI 類別名稱。附加元件以 `Dialogs::InnerWidget` 識別聊天室清單，因此不需要比對在地化後的無障礙名稱。主選單指令則以 UIA 座標命中測試在左上角尋找 Telegram 原生的按鈕，同時支援 `Dialogs::Widget` 與資料夾側欄兩種版面，必要時再回到既有的提供者端子樹查詢。

Telegram 的通話面板把每個控制項都建立成 `Ui::CallButton`，由左至右排列為分享畫面、攝影機、取消或拒接、接聽或掛斷、麥克風、加入成員。其中只有攝影機與麥克風帶有裝置選擇的角落按鈕，因此附加元件以該角落按鈕辨識這兩者，其餘則依它們在這一排中的位置辨識。尋找控制項時完全不讀取翻譯後的名稱；只有在報出動作時才讀取名稱，因為每個按鈕的名稱就是按下後會執行的動作。

所有指令都由全域外掛程式擁有，並以限定的擁有者解析本附加元件的 app module，避免其他附加元件搶走共用的 `appModules/telegram.py` 名額。指令只定義一次、且定義在一直執行的外掛程式中，NVDA 的「輸入手勢」對話方塊才會為每個指令保留單一且可重新指定的項目；每個指令會自行檢查前景視窗，並在 Telegram 不在前景時將按鍵傳給該程式。

## 社群與支援

* **Telegram 官方頻道**：[tdesktopnvda](https://t.me/tdesktopnvda)
* **Telegram 使用者群組**：[tdesktopnvda_group](https://t.me/tdesktopnvda_group)
* **原始碼與問題追蹤**：[keyang556/tdesktopnvda](https://github.com/keyang556/tdesktopnvda)
* **開發者聯絡方式**：[Ken Chang](https://t.me/Keyang556) <lindsay714322@gmail.com>

## 支援版本

* Telegram Desktop for Windows 7.0.1 或更新版本。
* NVDA 2024.1 或更新版本。

## 從原始碼建置

在此存放庫根目錄執行：

```powershell
uv run scons
```

產生的 `.nvda-addon` 套件可透過 NVDA 附加元件商店安裝。
