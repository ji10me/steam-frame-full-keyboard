# ダッシュボードとローカルアプリのJIS統一（実験用）

Full Keyboard 0.8.2を導入済みのSteam Frame向けの、任意で導入する追加ツールです。
標準キーボードの呼び出しを同じGraphiteテーマのJISキーボードに振り分けます。
Steam本体のファイルやシステム全体のキー配列は変更しません。

- Steamの入力欄：内蔵の日本語ローマ字変換と、元のSteam入力先を保持するブリッジを使用します。
- KDEデスクトップ／Chrome：既存のIBus・Anthyと物理JIS入力を使用します。
- PC配信ウィンドウ：物理JIS入力を送り、PC側のIMEを使用します。出現時は旧キーボードに近い手前の位置・約50度の傾きに揃え、その後は移動ハンドルで自由に移動・サイズ変更できます。

対応するウィンドウ下部のキーボードボタンは、標準キーボードを表示する前にJISへ直接振り分けます。開く・閉じる・再表示で標準キーボードを経由しません。Steamの入力欄では、元の入力先を保持する従来の置換経路を使用します。

アプリ用キーボードの初期高さは、`~/.local/state/frame-jis-keyboard/native-placement.json`の
`height_offset_m`で調整できます。`0.02`は標準の位置から真上へ2cmです。
反映には制御ツールの再起動が必要です。表示後の自由な移動には影響しません。
Steam用の位置は、上記とは別にSteam用設定の`placement.json`へ保存されます。

外部JISをそのままネイティブ置換に指定すると0.8.2では置換対象外となります。
また、このFrameの構成ではGamescopeへの日本語Unicode出力に問題があるため、
Steam用とローカルアプリ用の入力経路を分けています。表示するキー配列は両方ともJISです。
Steam用では半角／全角が内蔵変換を切り替え、ローカル用ではJISの物理キーを送ります。

### Steamメニューでもシンプルな表示を使う

`simple_japanese_ui`に対応したビルドでは、Steam用の
`~/.config/framekeyboard-unified-jis/steam/config.json`に
`"simple_japanese_ui": true`を追加すると、追加の変換・確定ボタンを省けます。
配列とキーの位置は通常のJIS表示と同じで、入力中の文字だけ上部に表示します。
日本語変換は内蔵エンジンをそのまま使います。Spaceまたは変換キーで変換、
Space・上下キーで候補切り替え、Enterで確定、半角／全角で英数に切り替えます。
反映にはSteam用キーボードサービスの再起動が必要です。
従来の配布済み0.8.2バイナリーはこの項目を無視するため、設定だけでは表示は変わりません。

## 導入

先に[デスクトップJIS設定](../jis-desktop/README.ja.md)を導入して、日本語入力を確認してください。
開発用PCからこのフォルダーのファイル一式をFrameの作業用フォルダーへ転送します。Pythonスクリプトに加え、`frame-jis-keyboard`、`frame-jis-systemui-session`、`systemui_router.js`も必要です。
Frameにリポジトリーをチェックアウトしたり、Frameでビルドしたりする必要はありません。

Frameで実行します。

```sh
python3 install.py
systemctl --user start frame-jis-keyboard.service
```

これで現在のSteamVRセッションに適用されます。再起動後も使う場合だけ、明示的に有効化します。

起動時にVRメニューのローカル接続を準備します。初回、またはVRメニュー単独の再起動後には、メニュー表示部分を読み直す場合があります。SteamVRサーバー、コンポジター、配信設定は変更しません。接続準備に失敗した場合は従来の置換経路を利用できます。

```sh
systemctl --user enable frame-jis-keyboard.service
```

`install.py --enable-startup`でも同じ自動起動設定を行えます。
Steam用の私有設定の`start_with_steamos`は隠して起動するためのアプリ側条件です。
実際の自動起動は上記のsystemd設定で制御します。
アプリ自身の起動設定の管理情報は専用の`XDG_CONFIG_HOME`に分離し、通常のユーザーサービス設定と競合させません。

通常ウィンドウ方式のPC配信は、配信側の`panel.json`に登録された現在のFrameキーを使います。
Flatpakインスタンス・実プロセス・開始時刻が一致した場合だけPC用設定を選び、
LinuxデスクトップのIMEを起動せずWindows向けの物理JIS入力を送ります。
従来の`valve.steam.desktopgame.2000000420`も互換用に対応しています。
配信プログラムは別プロジェクトに置き、この追加ツールには含めていません。
デスクトップの既存のFull Keyboard表示／非表示ショートカットは新しい制御ツールへ切り替わります。

```sh
~/.local/bin/frame-jis-keyboard toggle
~/.local/bin/frame-desktop-keyboard
~/.local/bin/frame-jis-keyboard hide
~/.local/bin/frame-jis-keyboard status
```

## 保存場所と復元

- `~/.local/share/framekeyboard/unified-jis/runtime/`：既存の確認済み0.8.2を複製した実行環境。元のMITライセンス等を保持します。Steam専用に外部ネイティブガードを除き、初期の同一Steam入力先を引き継ぐ限定拡張を加えます。
- `~/.config/framekeyboard-unified-jis/{steam,desktop,pc}/`：入力先ごとの設定と配置。従来の`~/.config/framekeyboard`は保持します。
- `~/.local/state/frame-jis-keyboard/`：導入前のバックアップ、入力先メタデータと検証結果。入力文字、パスワード、クリップボードは記録しません。

直接呼び出しには、Steamの既存の`127.0.0.1:8080`に加え、VRメニューの`127.0.0.1:9223`を使用します。追加の接続はループバックに限定し、VRメニューのデバッグ設定は準備後に元へ戻します。次回起動時には再びセッション用接続を準備します。

元のランチャーとユーザーサービスへ戻すには、転送した`restore.py`を実行します。

```sh
python3 restore.py
```

追加ツールの私有設定とバックアップは確認用に残ります。
PC配信側のキーボードショートカットはこの追加ツールを必要とします。

## 検証

開発用PCではNode.jsとPythonを用いて、既存ブリッジの回帰試験と、
起動時の同一入力先引き継ぎ・準備未完了・入力先変更・復元の試験を実行します。
C++本体やバイナリーの変更はありません。

```sh
python verify.py --node /path/to/node
python test_placement.py
python test_systemui_transport.py
python test_local_close.py
/path/to/node test_systemui_router.js systemui_router.js
```

Frameでは現在のデスクトップの正確なオーバーレイキーを指定します。
次の検証はタブを選び直し、標準ボタンと同じOpenVR要求で開閉します。文字は送信しません。
`--fault-test`は制御プロセスを強制終了する復旧試験も行うため、作業中の入力を終えてから実行します。

```sh
python3 validate_frame.py gamescope.gamescope-0.window.N --fault-test
python3 validate_footer.py
python3 validate_footer.py gamescope.gamescope-0.window.N
python3 validate_footer_fault.py
python3 validate_close.py
```

変換・確定の最終確認は実際の入力欄で行ってください。
直接振り分けを使える下部ボタンでは、標準キーボードを表示しないことを実機で確認しています。
アプリが直接発行するネイティブ要求や接続準備に失敗した場合には、標準表示を経由する従来の経路を使用することがあります。
表示後に隠す旧実験処理は使用していません。制御処理の停止時には、JISの終了を確認してから元の入力先の標準キーボードへ戻します。
右上の×で正常に閉じた場合は、同じ入力先の標準キーボードも閉じて、その要求を終了します。正常終了を異常終了時の復旧と区別するため、×を押しても標準キーボードへ切り替わりません。次に下部ボタンを押すとJISを開き直せます。
出現時の配置は毎回揃えます。表示中は位置を強制更新しないので、動かしても元の位置へ戻されません。
大きいシアター画面や遠い画面では、画面の下端に比例させず、頭の位置を基準に手元へ表示します。表示後の移動・サイズ変更は自由に行えます。
デスクトップ／PCからSteamへ入力先を切り替える際には、準備に約1秒かかります。
その途中で開いたキーボードが閉じた場合は、準備後にもう一度キーボードボタンを押してください。
未対応の要求、入力先を確認できない要求、Steamのインターフェース変更時には標準キーボードを残します。
Steam Linkで動作するVRゲーム内部のキーボードを置き換える機能ではありません。
