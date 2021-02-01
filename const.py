# 定数定義
import pathlib

# anyrunのAPI-Key
ANYRUN_APIKEY = ''

# Any.runからダウンロードした各種ファイルの保存先フォルダパス
DOWNLOAD_DIRECTORY = ''

# MISP登録設定
# 登録対象MISPのURL
MISP_URL = ''
# MISP登録を行いたいユーザーのAuthkeyを設定
MISP_AUTHKEY = ''

# メール設定
MAIL_FROM = 'ANYRUN登録結果<{}>'.format('')
MAIL_TO = ''
MAIL_SUBJECT = ''
MAIL_SMTP_SERVER = ''
MAIL_SMTP_USER = ''
MAIL_SMTP_PASSWORD = ''
ERROR_SUBJECT_PREFIX='[error]'


# 以下は原則変更不要
# anyrunの解析結果report一覧へのURL
HISTORY_URL_SITE = 'https://api.any.run/v1/analysis/'
# 登録したイベントの最新の日付をこのファイルに記録し、次回Script実行時にここに記載された日付より前のものは登録をしない
EVENT_DATE_DAT = pathlib.Path(__file__).resolve().parent.joinpath('event_date_dat')
# イベントをインポートする際のエラー発生時のリトライ回数
RETRY_MAXIMUM_LIMIT = 5
# イベントをインポートする際のエラー発生時に指定値文処理を停止
COMMAND_INTERVAL_TIME = 10
#イベントのインポート時に既に登録されているイベントの場合に発生するエラー出力を補足する為の文字列
DUPLICATE_EVENT_CONFIRM_WORD = 'Event already exists'
