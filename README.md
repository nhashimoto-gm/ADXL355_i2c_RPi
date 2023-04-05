# ADXL355_RPi

## 使用センサー
アナログ・デバイセズのADXL355。

( https://www.analog.com/jp/products/adxl355.html )

ストロベリーリナックスのADXL355 DIP化商品

( http://strawberry-linux.com/catalog/items?code=12355 )

## 接続機器と接続方法
RaspberryPIにi2c接続で通信。

(留意点１) 3.3VをVSUPPLYとVDDIOに供給。SCLK/VSSIOとMISO/ASELはGNDに接続。

i2cアドレスを0x1Dとしています。( MISO/ASELがLow ) ※Highで0x53となる。

(留意点２) プルアップ抵抗は3k-5kΩ。( 3.7kΩだったかな )

## 測定レンジについて
range4G設定にしてあります。( 128,000LSB/g ±4.096g-range )

この場合の計算式は、以下のとおり。

```
"x-axis":allAxes['x']/128000.0,"y-axis":allAxes['y']/128000.0,"z-axis":allAxes['z']/128000.0
```
>range2G設定 -> 256,000LSB/g ±2.048g-range
>
>range8G設定 ->  64,000LSB/g ±8.192g-range

## 注意
最初はprint文のコメント外し、Influxdb書き込み部分をコメントアウトして要確認。

LOCAL NETWORK上のInfluxdb v1.8サーバーへデータを送信。

InfluxQLは以下のような形で情報取得。(Grafana等利用)
```
SELECT mean("x-axis") FROM "autogen"."adxl355_measure" WHERE $timeFilter GROUP BY time(1s) fill(previous)
```

## Acknowledgments ( 謝辞 )

Markrad, you have been very helpful.

https://github.com/markrad/ADXL355
