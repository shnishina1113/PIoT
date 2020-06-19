import socket
import time
import nfc
import mysql.connector

#上位リンク通信設定
host_ip = '192.168.0.140'    # kv-8000のIPアドレス
host_port = 8501            # 上位リンク通信のポート番号
comand_bit = "RD MR7"       # PLCの読み取り指示ビット
end_bit = "WR DM12 13"        # PLCへの読み取り完了伝達ビット
time_registers = ["RD CM700","RD CM701","RD CM702","RD CM703","RD CM704","RD CM705"]
data_registers = ["RD DM10","RD DM11","RD DM12","RD DM13"]#読み取りデータレジスタ
separator = "\r"# 区切り符号CRの16進数表記
time_data = '' #時刻データ初期化
sql_data = []              #SQLに投げるDatalist初期化
#SQL接続設定
mysql_config ={
    'host' : '192.168.0.200',#サーバのIPアドレス
    'port' : '3306',#サーバのポート番号
    'user' : 'piot1',
    'password' : 'piot1',
#    'database' : 'PIoTdb',
    'database' : 'piottestdb',
}

class ether_connector:
    def __init__(self,host_ip,host_port,comand_bit,separator):
        self.host_ip = host_ip
        self.host_port = host_port
        self.comand_bit = comand_bit
        self.separator = separator
        
    def ether_connect(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # socket.AF_INETでip4を使うことを指定。socket.SOCK_STREAMでTCPを使うことを指定。
        client.connect((self.host_ip,self.host_port))
        # サーバーに接続(kv-8000にTCP接続/上位リンク通信)
        msg = self.message(self.comand_bit,self.separator)
        client.send(msg.encode("ascii"))
        # 上位リンク通信のデータコードがASCIIなのでエンコード
        #print("send : " + msg)
        response = client.recv(1024)
        response = response.decode("UTF-8")
        # PLCからの返答がbyteデータなのでUTF-8にデコード
        client.close()
        return response
    
    def message(self,comand_bit,separator):
        message = comand_bit + separator
        print(message)
        return message


class rfid_reader:
    def rfid_read(self):
        clf = nfc.ContactlessFrontend('usb')
        tag = clf.connect(rdwr={'on-connect': lambda tag: False})
        print(tag.ndef.records[0])
        rfid = str(tag.ndef.records[0])
        #読み取り内容から必要なVFから始まるジグ情報部分を抜き出し
        id_c ='C' + rfid[rfid.find('VF-')+11:rfid.find('VF-')+15]
        clf.close()
        return id_c
class sql_connector:
    def __init__(self,mysql_config):
        self.mysql_config = mysql_config
        self.sql_data = sql_data
    def sql_connect(self,sql_data):
        mysql_con = mysql.connector.connect(**self.mysql_config)
        cursor = mysql_con.cursor()
        cursor.execute("INSERT INTO PULSEHEAT VALUES ('{0[0]}','{0[1]}','{0[2]}','{0[3]}','{0[4]}','{0[5]}');".format(sql_data))
        mysql_con.commit()
        mysql_con.close()

while True:
    tcp_connection = ether_connector(host_ip,host_port,comand_bit,separator)    
    response = int(tcp_connection.ether_connect())
    print("Received :" ,response)#PLCの指令ビット待ち
    
    if response == 1:
        #指令が立ったらRFIDを読む
        id_num = rfid_reader().rfid_read()
        print('Pallet ID:',id_num)
        #RFIDからIDを読み取り、SQLに投げるlistに格納
        sql_data.append(id_num)
        #時間読み出しは別処理し、Dataをlistに格納
        for i in range(len(time_registers)):
            tcp_connection = ether_connector(host_ip,host_port,time_registers[i],separator)    
            response = int(tcp_connection.ether_connect())
            if response < 10:#既存SQLDataと整合のため、データ整形
                response = '0' + str(response)
            time_data = time_data + str(response)
            print(time_data)
        time_sql = '20' + time_data
        print(time_sql)
        sql_data.append(time_sql)
        #読みたいDMの数だけPLCに接続し、Dataをlistに格納
        for i in range(len(data_registers)):
            tcp_connection = ether_connector(host_ip,host_port,data_registers[i],separator)    
            response = int(tcp_connection.ether_connect())
            sql_data.append(response)
        print(sql_data)
        #SQLにINSERTする
        sql_connection = sql_connector(mysql_config).sql_connect(sql_data)
        #PLCにData吸出しが終了したことを伝え、comand_bitをoffにしてもらう
        tcp_connection = ether_connector(host_ip,host_port,end_bit,separator)    
        response = tcp_connection.ether_connect()
        #初期化
        time_data = ''
        time_sql = ''
        sql_data = []
        
    time.sleep(0.5)