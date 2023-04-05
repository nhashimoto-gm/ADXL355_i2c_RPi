# ADXL355_RPi
センサーはアナログ・デバイセズのADXL355。
(https://www.analog.com/jp/products/adxl355.html)

RaspberryPIにi2c接続で通信。
プルアップ抵抗は3k-5kΩ。( 3.7kΩだったかな。
range4G設定にしてあります。128,000LSB/g ±4.096g-range
この場合の計算式は、以下のとおりです。
"x-axis":allAxes['x']/128000.0,"y-axis":allAxes['y']/128000.0,"z-axis":allAxes['z']/128000.0

*range2G設定 -> 256,000LSB/g ±2.048g-range
*range8G設定 ->  46,000LSB/g ±8.192g-range

最初はprint文のコメント外し、Influxdb書き込み部分をコメントアウトして確認してみてください。

LOCAL NETWORK上のInfluxdb v1.8サーバーへデータを送信。
InfluxQLは以下のような形で情報取得。(Grafana等利用)
SELECT mean("x-axis") FROM "autogen"."adxl355_measure" WHERE $timeFilter GROUP BY time(1s) fill(previous)
