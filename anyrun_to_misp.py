#!/usr/bin/env python3

#*# モジュールインポート
#-- 標準ライブラリ
import time
import json
import traceback
import pathlib
import sys
from datetime import datetime as dt
from typing import Union,List,Dict

#-- pip インストールモジュール
import requests
from pymisp import ExpandedPyMISP, MISPEvent

#-- 独自モジュール
import const
from MailSender import MailSender

# secureWarningを抑制
import urllib3
from urllib3.exceptions import InsecureRequestWarning
urllib3.disable_warnings(InsecureRequestWarning)

# グローバル変数
# anyrunリクエスト時に指定するヘッダ
anyrun_headers = {
	'Authorization': f'API-Key {const.ANYRUN_APIKEY}'
}

# Functions:

def constant_check(constant_data: Union[str, int, pathlib.Path], constant_name:str) -> bool:
	""" 定数値に有効な値が設定されているかをチェックする。
		constant_data: const.pyで設定されていた定数値
		constant_name: 該当定数の定数名（エラーメッセージ出力時「に利用）
			return: 有効な場合はTrue、無効な場合はFalse
	"""

	# エラーメッセージは共通のため定義しておく
	error_msg = f'const.py: {constant_name}に値が設定されていません。正しい値を設定して、再実行してください。'

	# Noneはエラー
	if constant_data is None:
		print(error_msg)
		return False

	# 文字列（str)で空白はエラー
	if isinstance(constant_data,str) and constant_data == '':
		print(error_msg)
		return False

	# 数値はマイナスならエラー
	if isinstance(constant_data, int) and constant_data < 0:
		print(error_msg)
		return False

	# pathlibの場合は、ひとまずファイル名が設定されていればOKとする（書き込みができる・できないなどは利用箇所の要件に合わせて別途チェック）
	if isinstance(constant_data, pathlib.Path) and constant_data.name == '':
		print(error_msg)
		return False

	# どの条件にもマッチしなかった場合正常値と判断
	return True

def get_history(event_date_log:str, download_directory_path:pathlib.Path) -> list:
	""" 履歴情報を取得し、URLリストを返す
			return: 各anyrunの分析結果ファイル（３ファイル）の辞書のリスト[{'misp':MISPフォーマットファイルURL,'ioc':IOCファイルのURL,'summary':サマリファイルのURL}]
 """
	print('historyのデータ取得開始:{}'.format(dt.now().strftime('%Y-%m-%d %H:%M:%S')))

	# history用の変数
	skip_count = 0
	skip_count_plus = 25

	# history一覧を取得
	url_list:List[Dict[str,str]] = []

	while True:

		# 分析結果reportの一覧を取得
		params = {
			'skip': skip_count
		}

		history = None
		try:
			history = requests.get(const.HISTORY_URL_SITE, headers=anyrun_headers, params=params)
			if history.status_code != 200:
				history.raise_for_status()

		except:
			print('anyrunとの接続に問題が発生しました。const.pyに設定されているanyrunのAPIキーを確認してください。\nAPIキーに問題がない場合は、以下エラー情報をご確認ください。')

			# レスポンスが取得できている場合はそのレスポンス情報を出力
			if history is not None:
				print(f'レスポンスコード: {history.status_code}')
				print(f'レスポンス内容: {history.text}')

			# レスポンスが取得できていない場合は例外情報を出力
			else:
				print(traceback.format_exc())

			sys.exit()

		# json.loadし、key'data'を取得、同一覧をファイルにダウンロード
		history_values = json.loads(history.text)
		history_file = download_directory_path.joinpath(f'history_skip_{skip_count}.json')
		with history_file.open('w') as f:
			json.dump(history_values, f, indent=2, ensure_ascii=False)

		# history一覧から、各reportのURL一覧のリスト作成
		url_data_dicts = history_values.get('data', {}).get('tasks', [])

		print(f'skip値: {skip_count}')

		# 履歴データがそれ以上存在しない場合空のりすとを返すので、そこをイベント登録の最後として処理を終了
		if url_data_dicts == []:
			print('最古の履歴情報まで取得しました。')
			return url_list

		for url_data_dict in url_data_dicts:
			event_date = url_data_dict['date']
			# 前回処理済み時間が今回の履歴情報より新しくなった場合は処理終了
			if event_date_log >= event_date:
				print(f'これ以降はインポート済みイベントのためスキップします: {event_date}')
				return url_list

			url_to_summary = url_data_dict['json']
			url_to_misp = url_data_dict['misp']
			# url_to_summaryのURLの末尾をioc_report用に置換
			url_to_ioc = url_to_summary.replace('/summary/json', '/ioc/json')
			# dateはそのままではファイル名に出来ない文字が含まれる為、それらを置換
			event_file_date = event_date.replace(':', '').replace('.', '')
			url_list.append({ 'summary': url_to_summary ,'misp': url_to_misp ,'ioc': url_to_ioc ,'date': event_file_date , 'analysisdate': event_date })

		skip_count += skip_count_plus

	return url_list

def download_file(target_url:str, report_file:pathlib.Path) -> tuple:
	"""
	戻り値1: 値が存在すれば dict,ファイル数をカウントする為 1 を返す
	戻り値2: 値が存在しなければ None, ファイル数をカウントする為 0 を返す
	"""
	try:
		report_data = requests.get(target_url, headers=anyrun_headers)
		report_dict = json.loads(report_data.text)
		with report_file.open('w') as f:
			json.dump(report_dict, f, indent=2, ensure_ascii=False)
	except:
		print('ダウンロードしたファイルに何らかの問題が発生しました')
		print(target_url)
		print(traceback.format_exc())
		return None, 0
	else:
		return report_dict, 1

def create_misp_event(misp_data:dict, ioc_data:list, error_files:list) -> dict:
	"""
	MISPフォーマットファイルのデータとIOCファイルのデータを元にMISP登録用データを作成する
	戻り値1: MISP登録用データ作成結果 dict型
	"""

	# resultにiocreportの必要な個所をリスト科、ioc_valuesにmisp_format_listとの比較用リストの作成
	ioc_reputation_tag = ''

	result = []

	for ioc_dict_list in ioc_data:
		ioc_category = ioc_dict_list['category']
		ioc_type = ioc_dict_list['type']
		ioc_reputation = str(ioc_dict_list['reputation'])
		ioc_value = ioc_dict_list['ioc']

		if ioc_reputation == '0':
			ioc_reputation_tag = 'anyrun:reputation:unknown'
		elif ioc_reputation == '1':
			ioc_reputation_tag = 'anyrun:reputation:suspicious'
		elif ioc_reputation == '2':
			ioc_reputation_tag = 'anyrun:reputation:malicious'
		elif ioc_reputation == '4':
			ioc_reputation_tag = 'anyrun:reputation:unsafe'
		else:
			ioc_reputation_tag = ''
			error_files.append(f'reputation_error: {ioc_value} / reputation値: {ioc_reputation}')

		if 'Main object' == ioc_category:
			result.append({'category':'Payload delivery','type':ioc_type,'value':ioc_value, 'comment': 'Main object', 'Tag': [{'name': ioc_reputation_tag}]})

		elif 'Dropped executable file' == ioc_category:
			ioc_name = ioc_dict_list['name']
			ioc_hash_type = f'filename|{ioc_type}'
			ioc_file_hash = f'{ioc_name}|{ioc_value}'
			result.append({'category':'Artifacts dropped','type':ioc_hash_type,'value':ioc_file_hash, 'comment': '', 'Tag': [{'name': ioc_reputation_tag}]})

		elif 'DNS requests' == ioc_category:
			result.append({'category':'Network activity','type':ioc_type,'value':ioc_value, 'comment': '', 'Tag': [{'name': ioc_reputation_tag}]})

		elif 'Connections' == ioc_category:
			result.append({'category':'Network activity','type':'ip-dst','value':ioc_value, 'comment': '', 'Tag': [{'name': ioc_reputation_tag}]})

		elif 'HTTP/HTTPS requests' == ioc_category:
			result.append({'category':'Network activity','type':'url','value':ioc_value, 'comment': '', 'Tag': [{'name': ioc_reputation_tag}]})

		else:
			error_files.append(f'undefined_category: {ioc_category} / type: {ioc_type} / value: {ioc_value}')

	# MISPのイベントのpublished設定値をTrueに設定
	misp_data['Event']['published'] = True
	misp_Attributes = misp_data['Event']['Attribute']

	# MISPフォーマットデータ中の参考情報リンクをイベント登録情報に追加する
	for misp_Attribute in misp_Attributes:
		misp_type = misp_Attribute['type']
		misp_value = misp_Attribute['value']
		misp_distribution = misp_Attribute['distribution']
		if 'link' == misp_type:

			# 参考情報の末尾に	/	がない場合、/を追加する
			if misp_value.endswith('/') == False:
				misp_value = f'{misp_value}/'

			result.append({'category':'External analysis','type':'link','value':misp_value,'distribution':misp_distribution, 'comment': ''})

	misp_data['Event']['Attribute'] = result

	return misp_data

def register_misp(misp:ExpandedPyMISP, misp_event_dict:dict) -> None:
	""" MISPイベントデータを受け取り、MISPに登録する """

	misp_event = MISPEvent()
	misp_event.from_dict(**misp_event_dict)
	threat_level_id = misp_event.get('threat_level_id')
	threat_level = f'anyrun:threat_level:{threat_level_id}'
	misp_event.add_tag('anyrun')
	misp_event.add_tag(threat_level)

	retry_count = 0
	while True:
		try:
			# pymispをインスタンス化してイベント登録
			event_data = misp.add_event(misp_event)
			if event_data.get('errors'):
				raise Exception(event_data['errors'])

			# MISPに登録されるイベントIDを取得し、出力
			event_id = event_data['Event']['id']
			print(f'新規に登録されたEvent_ID: {event_id}')

			return

		except:
			except_return = traceback.format_exc()

			# インポート済みの場合
			if const.DUPLICATE_EVENT_CONFIRM_WORD in except_return:
				print('Importを行おうとしたイベントは既にMISPに登録されています')
				return

			# リトライ回数チェック
			retry_count += 1
			if retry_count >= const.RETRY_MAXIMUM_LIMIT:
				raise

			# インターバル処理
			print('MISPへのイベントインポートをリトライします')
			time.sleep(const.COMMAND_INTERVAL_TIME)

#メール設定
def mail_send(mail_buffer:list) -> None:
	print('メール送信内容：')
	print('\n'.join(mail_buffer))

	if const.MAIL_TO is None or const.MAIL_TO == '':
		print('メール送信先未設定のため、メール送信処理は行われません')
		return

	sender = MailSender(
		from_address=const.MAIL_FROM
		,smtp_server=const.MAIL_SMTP_SERVER
		,smtp_user=const.MAIL_SMTP_USER
		,smtp_password=const.MAIL_SMTP_PASSWORD
	)

	sender.send(const.MAIL_TO
		, mail_subject
		, '\n'.join(mail_buffer)
	)

if __name__ == '__main__':

	# const.py設定値チェック
	# Scriptの動作に必須の定数が未設定の場合、処理を中断
	check_result = []
	check_result.append(constant_check(const.ANYRUN_APIKEY, 'ANYRUN_APIKEY'))
	check_result.append(constant_check(const.DOWNLOAD_DIRECTORY, 'DOWNLOAD_DIRECTORY'))
	check_result.append(constant_check(const.MISP_URL, 'MISP_URL'))
	check_result.append(constant_check(const.MISP_AUTHKEY, 'MISP_AUTHKEY'))
	check_result.append(constant_check(const.HISTORY_URL_SITE, 'HISTORY_URL_SITE'))
	check_result.append(constant_check(const.EVENT_DATE_DAT, 'EVENT_DATE_DAT'))
	check_result.append(constant_check(const.RETRY_MAXIMUM_LIMIT, 'RETRY_MAXIMUM_LIMIT'))
	check_result.append(constant_check(const.COMMAND_INTERVAL_TIME, 'COMMAND_INTERVAL_TIME'))
	check_result.append(constant_check(const.DUPLICATE_EVENT_CONFIRM_WORD, 'DUPLICATE_EVENT_CONFIRM_WORD'))
	# 一つでもエラーがあれば終了
	if False in check_result:
		print('Scriptの動作に必須の定数が未設定の為、処理を中断します')
		sys.exit()

	print('Script実行開始')
	start_time = dt.now().strftime('%Y/%m/%d %X')
	print(start_time)

	# Script処理結果のメール件名
	# 設定値内に{}があれば日時を埋め込む
	mail_subject = f'{const.MAIL_SUBJECT}: {dt.now().strftime("%Y/%m/%d %X")}'

# Script処理結果をメール本文に追記する変数
	mail_buffer = []
	mail_buffer.append('Script開始時間')
	mail_buffer.append(start_time)

	# エラー出力をメール本文に追記する変数
	error_files = []

	# ディレクトリ名に日付を使用する
	dir_name_time = dt.today().strftime('%Y%m%d')
	download_directory_path = pathlib.Path(const.DOWNLOAD_DIRECTORY).joinpath(dir_name_time)

	# script実行時に更新のあるファイルのダウンロードフォルダ作成
	download_directory_path.mkdir(parents=True, exist_ok=True)

	# 前回登録したイベントの日付を記録したファイルの存在確認
	if const.EVENT_DATE_DAT.is_file() == False:
		const.EVENT_DATE_DAT.touch()

	# 登録済みのイベントの日付を取得
	with const.EVENT_DATE_DAT.open(mode='r') as f:
		event_date_log = f.read()

	# any.runから履歴を取得して、対象となるURLリストを取得する
	url_list = get_history(event_date_log, download_directory_path)

	# イベントの更新がない場合はNone、値が存在すればhistoryの最新の日付を取得
	if url_list == []:
		# イベントの更新がない場合はその旨とScript開始時間と終了時間のみメールで通知
		mail_buffer.append('本日の更新はありませんでした')
		mail_buffer.append(f'Script終了時間: {dt.today().strftime("%Y/%m/%d %X")}')
		mail_send(mail_buffer)
		sys.exit()

	# historyから取得したURLリストをループし、順次MISPへ登録する
	# 各ファイルの結果をカウントする為の変数
	normal_count = 0
	error_count = 0
	file_count_result = 0
	loop = 0

	# MISP接続
	misp = ExpandedPyMISP(const.MISP_URL, const.MISP_AUTHKEY, ssl=False, debug=False)

	# 各ファイルと日付データをダウンロードし、中身を変数に取得
	for url_info in url_list:
		loop += 1
		misp_file_url = url_info['misp']
		import_target_url = misp_file_url.rsplit('/',2)[0]
		print(f'インポート対象分析結果URL: {import_target_url}')

		try:
			# 各レポートのhistoryへの登録日を取得
			analysis_date = url_info['analysisdate']

			# 各レポートの名前の作成時に使用するファイル名用に返還された日付
			report_date = url_info['date']

			# ダウンロードしたファイルにそれぞれのレポート用の名前をつける
			misp_file = download_directory_path.joinpath(f'misp_{loop}_{report_date}.json')
			ioc_file = download_directory_path.joinpath(f'ioc_{loop}_{report_date}.json')
			summary_file = download_directory_path.joinpath(f'summary_{loop}_{report_date}.json')

			# history一覧からファイルをダウンロードする。
			# misp_dataとioc_dataはMISPへの登録用データ、summary_dataはファイル確認用に使用
			misp_data, misp_report_success_count = download_file(url_info['misp'], misp_file)
			ioc_data, ioc_report_success_count = download_file(url_info['ioc'], ioc_file)
			summary_data, summary_report_success_count = download_file(url_info['summary'], summary_file)

			# ダウンロードしたファイルの確認
			error_files_date = f'データがエラーのファイル: {analysis_date}'
			if misp_data is None and ioc_data is None:
				error_files.append(error_files_date)
				error_files.append(url_info['misp'])
				error_files.append(url_info['ioc'])
				error_count += 1
				continue
			elif misp_data is None:
				error_files.append(error_files_date)
				error_files.append(url_info['misp'])
				error_count += 1
				continue
			elif ioc_data is None:
				error_files.append(error_files_date)
				error_files.append(url_info['ioc'])
				error_count += 1
				continue

			if summary_data is None:
				error_files.append(error_files_date)
				error_files.append(url_info['summary'])

			# ダウンロードに成功したファイル数をカウント
			file_count_result += misp_report_success_count + ioc_report_success_count + summary_report_success_count

			# MISPフォーマットファイルとIOCファイルを使って、登録用のMISPイベントを	作成
			misp_event = create_misp_event(misp_data, ioc_data, error_files)

			# MISPに登録
			register_misp(misp, misp_event)

			normal_count += 1

		except Exception as e:
			mail_subject = f'{const.ERROR_SUBJECT_PREFIX}{mail_subject}'
			error_file_hash = import_target_url.replace('https://api.any.run/report/', '')
			error_files_msg = f'except_error_hash: {error_file_hash}'
			error_files.append(error_files_msg)
			error_files.append(str(e))
			print('メイン処理中に予期せぬエラーが発生しました')
			print(import_target_url)
			print(traceback.format_exc())
			error_count += 1

	# 今回処理した分析データで最新の日付をファイルに保存
	last_analysis_date = url_list[0]['analysisdate']
	with const.EVENT_DATE_DAT.open('w') as f:
		f.write(last_analysis_date)

	end_time = dt.today().strftime('%Y/%m/%d %X')
	print(end_time)

	mail_buffer.append(f'History最新の日付: {last_analysis_date}')

	mail_buffer.append('イベント登録成功数 / 総登録予定イベント数')
	success_event = f'{normal_count}/{loop}'
	mail_buffer.append(success_event)

	mail_buffer.append('イベント登録に失敗した数 / 総登録予定イベント数')
	failure_event = f'{error_count}/{loop}'
	mail_buffer.append(failure_event)

	loop *= 3
	mail_buffer.append('正常にダウンロードされたファイル数 / 総ダウンロードファイル数')
	success_download = f'{file_count_result}/{loop}'
	mail_buffer.append(success_download)

	mail_buffer.append('エラーファイルがあればこちらに記載')
	mail_buffer.append('\n'.join(error_files))

	mail_buffer.append(f'Script終了時間: {end_time}')

	mail_send(mail_buffer)
	print('全工程を終了しました')
