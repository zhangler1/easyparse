docker build -f dockerfile.uv  --build-arg https_proxy=http://192.168.0.106:1087  --build-arg http_proxy=http://192.16
8.0.106:1087 --build-arg no_proxy=localhost,192.168.0.106,.local   --progress=plain .   
-t  easyparse