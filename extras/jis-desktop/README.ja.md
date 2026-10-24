# Steam Frame向け JISデスクトップ入力の追加設定

[English](README.md) | **日本語**

![変換キーを備えたJISキーボード](../../docs/images/keyboard-jis-graphite.png)

フルサイズのJIS配列でローマ字入力し、デスクトップにあるIBus/Anthyでかな漢字変換するための追加設定です。デスクトップを選んでキーボードを開閉する **Full Keyboard（表示／非表示）** ランチャーも含みます。

まず通常版のFull Keyboardをインストールしてください。このフォルダーはユーザープロファイルとヘルパーで構成され、新しいARM64実行ファイルを含みません。[通常版の導入手順](../../README.ja.md#通常版をインストールする)も参照できます。

## 必要な環境

- 入れ子のKDEデスクトップを使うSteam Frame。
- Python 3、IBus/Anthy、`busctl`、`gio`、`systemd-run`、`/opt/steamvr/bin/linuxarm64/vrcmd`。
- 標準のユーザーディレクトリへ導入済みのFull Keyboard 0.8.2。
- `~/.config`と`~/.local`を使う通常のホームディレクトリ構成。
- キーボードを開く前に、デスクトップが起動していること。
- **Replace native keyboard** と **Start with SteamOS** が無効であること。

この構成はSteamOS 0.4.5とChromeのX11/XIMで確認されています。ほかのアプリ、フローティングウィンドウ、今後のSteamOSでは別途確認してください。PCから配信するVRアプリへの入力は対象外です。

## 変更する内容

通常のJIS配列の形は維持し、**半/全キーの動作だけ**をFrameで使えるキーに合わせています。確認したデスクトップ配列ではLinux evdev 85が未割り当てで、41が`Zenkaku_Hankaku`に対応していました。そのため、このキーには論理アクション`Backquote`を使います。画面上の表記は「半/全」のままです。

言語プロファイルは実際の`jp106`／`jp`配列を使い、対応する物理アクションを必須キーとして定義しています。表示のラベルだけをJISにしたものではありません。

ヘルパーは、KDEの仮想キーボードUIとは別にAnthyを起動します。このキーボードを表示すると、対象デスクトップの自動仮想キーボードを無効にし、必要に応じて日本語IMEのユーザーセッションunitを起動してAnthyを選びます。標準VRキーボードはダッシュボードの通常の閉じる処理を通して閉じます。Steamのファイルや、標準のキーボード呼び出しボタンの割り当ては変更しません。

開閉はインストール済みFull Keyboardの正常終了処理を使います。停止する前に実行ファイルのパスとプロセスの起動時刻を確認し、表示時は`--target-language ja-jis-frame`付きの手動unitから起動します。ログイン時の自動起動は設定しません。

ヘルパーは入力文字、クリップボード、ブラウザーの入力欄、認証情報を収集しません。動作記録とバックアップは、ユーザーのホームディレクトリ内に保存されます。

## このフォルダーだけをFrameへコピーする

開発用PCから、このフォルダーだけを転送します。Frame本体にリポジトリ全体のチェックアウトを置く必要はありません。`FRAME_HOST`は自分のSSH接続先に読み替えてください。

```sh
scp -r extras/jis-desktop FRAME_HOST:~/Downloads/
```

Frameの **KDEデスクトップ内** で端末を開きます。保存設定の変更前にFull Keyboardを終了してください。起動中に編集すると、終了時に古い設定で上書きされることがあります。

次のコマンドで既存の設定をバックアップし、プロファイルとヘルパーをコピーします。表示されるバックアップ先を控えてください。

```sh
cd ~/Downloads/jis-desktop
backup="$HOME/.local/state/framekeyboard-jis-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
for relative in .config/framekeyboard .local/bin/framekeyboard-toggle \
  .local/bin/frame-jis-ime-start .local/share/applications/framekeyboard.desktop \
  .config/environment.d/60-framekeyboard-jis.conf; do
  if [ -e "$HOME/$relative" ] || [ -L "$HOME/$relative" ]; then
    mkdir -p "$backup/$(dirname "$relative")"
    cp -a "$HOME/$relative" "$backup/$relative"
  fi
done
printf 'Backup: %s\n' "$backup"

mkdir -p ~/.config/framekeyboard/layouts ~/.config/framekeyboard/languages \
  ~/.local/bin ~/.local/share/applications ~/.config/environment.d
install -m 644 layouts/ja-jis-frame.json ~/.config/framekeyboard/layouts/
install -m 644 languages/ja-jis-frame.json ~/.config/framekeyboard/languages/
install -m 755 bin/framekeyboard-toggle bin/frame-jis-ime-start ~/.local/bin/
```

続いて、他の設定を保持したままJISプロファイルを選び、手動の起動項目を作ります。

```sh
python3 - <<'PYSETUP'
import json
import os
from pathlib import Path

home = Path.home()
config = home / '.config/framekeyboard/config.json'
prefs = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {'schema_version': 1}
if prefs.get('replace_native_keyboard') or prefs.get('start_with_steamos'):
    raise SystemExit('Disable native replacement/startup in Settings first.')
prefs.setdefault('active', {}).update(layout='ja-jis-frame-full', language='ja-jis-frame')
prefs['active'].setdefault('theme', 'graphite')

def write(path, text):
    temporary = path.with_name(path.name + '.jis-new')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, path)

write(config, json.dumps(prefs, ensure_ascii=False, indent=2) + '\n')
write(home / '.config/environment.d/60-framekeyboard-jis.conf',
      'FRAMEKEYBOARD_TARGET_LANGUAGE=ja-jis-frame\n')
write(home / '.local/share/applications/framekeyboard.desktop',
      '[Desktop Entry]\nType=Application\nName=Full Keyboard (show/hide)\n'
      'Name[ja]=Full Keyboard\uff08\u8868\u793a\uff0f\u975e\u8868\u793a\uff09\n'
      'Exec=' + str(home / '.local/bin/framekeyboard-toggle') + '\n'
      'Icon=input-keyboard\nTerminal=false\nCategories=Utility;Accessibility;\n')
PYSETUP
update-desktop-database ~/.local/share/applications
```

環境変数のファイルは、今後のデスクトップセッションで読み込まれます。今回のランチャーは対応するtargetを直接渡すので、現在のセッションでも使えます。

通常版を再インストール・更新した後は、カスタム起動項目が置き換わっていないか確認してください。置き換わった場合は、上の起動項目を作る手順をもう一度実行します。ユーザープロファイルは通常の更新で保持されます。

## 日本語IMEとChromeの設定

デスクトップ内の端末で、ローマ字入力と起動時のひらがなモードを指定します。

```sh
gsettings set org.freedesktop.ibus.engine.anthy.common typing-method 0
gsettings set org.freedesktop.ibus.engine.anthy.common input-mode 0
```

起動済みのAnthyが現在の入力モードを保持する場合があります。新しいランチャーで開いた後、**半/全**で日本語と英数を選んでください。IMEは必要に応じて起動され、キーボードを非表示にしても動作します。

確認済みのFlatpak版Chromeでは、X11/XIMを使います。既存のフラグファイルがあればバックアップしてから追記し、Chromeを一度終了して開き直してください。

```sh
flatpak override --user --env=GTK_IM_MODULE=xim --env=XMODIFIERS=@im=ibus com.google.Chrome
mkdir -p ~/.var/app/com.google.Chrome/config
printf '%s\n' '--ozone-platform=x11' >> ~/.var/app/com.google.Chrome/config/chrome-flags.conf
```

この変更は、そのChromeのインストールに適用されます。キーボードの追加設定は、ブラウザープロファイル、Cookie、保存パスワード、ページ内容を編集しません。

## 使い方と確認

1. アプリ一覧の **Full Keyboard（表示／非表示）** を開きます。もう一度選ぶと閉じ、次に選ぶと再表示します。入力中はダッシュボードを開いておきます。
2. デスクトップのアプリで、個人情報を含まない確認用の入力欄を選びます。
3. `nihon` → Space → Enterで **日本** と入力されることを確認します。
4. **半/全**を押してから`nihon`と入力し、英字のままになることを確認します。もう一度**半/全**を押すと、日本語変換へ戻ります。

プロファイルの構文は通常アプリの`--check`で検証できます。検証や画像の描画は、入力先へキーを送りません。ただし、それだけでコントローラー操作やIMEの動作が保証されるわけではありません。利用するアプリの確認用入力欄でも試してください。

## 以前の構成へ戻す

Full Keyboardを終了し、バックアップしたファイルを復元します。追加前に存在しなかったファイルは、今回追加したものだけを取り除いてください。

デスクトップ内の端末からでも、IMEのunitを停止するときは外側のユーザーバスを指定します。

```sh
runtime="/run/user/$(id -u)"
XDG_RUNTIME_DIR="$runtime" DBUS_SESSION_BUS_ADDRESS="unix:path=$runtime/bus" \
  systemctl --user stop frame-desktop-jis-ime.service
```

以前KDEの自動仮想キーボードが有効だった場合は、デスクトップ内の端末で次を実行して戻します。この端末のセッションバスはKWin側のものです。

```sh
busctl --address="$DBUS_SESSION_BUS_ADDRESS" set-property org.kde.KWin \
  /VirtualKeyboard org.kde.kwin.VirtualKeyboard enabled b true
```

この設定のためだけにChromeの環境変数やフラグを変更した場合は、それらも元の状態へ戻してください。この追加設定では標準キーボード置換を有効にしていません。
