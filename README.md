# ADXL355_RPi

## 使用センサー
アナログ・デバイセズのADXL355。

(https://www.analog.com/jp/products/adxl355.html)

## 接続機器と接続方法
RaspberryPIにi2c接続で通信。

プルアップ抵抗は3k-5kΩ。( 3.7kΩだったかな。

## 測定レンジについて
range4G設定にしてあります。( 128,000LSB/g ±4.096g-range

この場合の計算式は、以下のとおり。

```
"x-axis":allAxes['x']/128000.0,"y-axis":allAxes['y']/128000.0,"z-axis":allAxes['z']/128000.0
```
>range2G設定 -> 256,000LSB/g ±2.048g-range
>
>range8G設定 ->  46,000LSB/g ±8.192g-range

## 注意
最初はprint文のコメント外し、Influxdb書き込み部分をコメントアウトして要確認。

LOCAL NETWORK上のInfluxdb v1.8サーバーへデータを送信。

InfluxQLは以下のような形で情報取得。(Grafana等利用)
```
SELECT mean("x-axis") FROM "autogen"."adxl355_measure" WHERE $timeFilter GROUP BY time(1s) fill(previous)
```
