import sys
import smtplib
from email import encoders
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import formatdate
import time
import traceback

class MailSender(object):
	""" メール送信クラス """

	def __init__(self, from_address:str, smtp_server:str, smtp_user:str, smtp_password:str, max_retry_count:int =10)->None:
		self.FROM_ADDRESS = from_address
		self.SMTP_SERVER = smtp_server
		self.SMTP_USER = smtp_user
		self.SMTP_PASSWORD = smtp_password
		self.max_retry_count = max_retry_count

	def send(self, to_address:str, subject:str, message:str, attachments:list = [], convert_crlf:bool = True)->bool:
		""" メールを送信する """
		msg = MIMEMultipart()
		msg["Subject"] = subject
		msg["From"] = self.FROM_ADDRESS
		msg["To"] = to_address
		msg["Date"] = formatdate(localtime=True)

		# 改行コードをCRLFに変換する
		if convert_crlf:
			message = '\r\n'.join(message.splitlines())

		body = MIMEText('{}'.format(message))

		msg.attach(body)

		for attach_info in attachments:

			attachment = MIMEBase(attach_info['mime']['type'],attach_info['mime']['subtype'])
			with open(attach_info['filepath'], 'rb') as f:
				attachment.set_payload(f.read())

			encoders.encode_base64(attachment)
			attachment.add_header("Content-Disposition","attachment", filename=attach_info.get('filename', ''))
			msg.attach(attachment)

		retry_count = 0

		while retry_count <= self.max_retry_count:

			try:
				smtp = smtplib.SMTP_SSL(self.SMTP_SERVER)
				smtp.login(self.SMTP_USER, self.SMTP_PASSWORD)
				smtp.send_message(msg)
				smtp.quit()
				return True

			except:
				print(traceback.format_exc())
				print('Mail send failed.retry: {}/{}'.format(retry_count, self.max_retry_count))
				time.sleep(10)
				retry_count = retry_count + 1

		print('Mail send failed.')
		return False
