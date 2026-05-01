░▒▓  ~   08:18 
❯ ssh -p 26592 root@i-1.gpushare.com
The authenticity of host '[i-1.gpushare.com]:26592 ([122.9.140.87]:26592)' can't be established.
ED25519 key fingerprint is SHA256:/F3HNJMpjhDkDiyeRdENu3uNFQ9IB7Qn1sFyPT2n3eY.
This key is not known by any other names
Are you sure you want to continue connecting (yes/no/[fingerprint])? y
Please type 'yes', 'no' or the fingerprint: yes
Warning: Permanently added '[i-1.gpushare.com]:26592' (ED25519) to the list of known hosts.
Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-153-generic x86_64)
使用前请先阅读「数据目录」文档，不要在其他目录存放大容量数据。
快速入门：https://gpushare.com/docs/getting-started/quickstart/
数据目录：https://gpushare.com/docs/data/storage/
╔══════════╦════╦══════════╦════╦══════════╦════╗
║   目录   ║类型║   作用   ║权限║随实例迁移║速度║
╠══════════╬════╬══════════╬════╬══════════╬════╣
║/hy-tmp   ║本地║存训练数据║读写║   否     ║最快║
║/hy-public║云盘║公共数据  ║只读║   是     ║慢  ║
╚══════════╩════╩══════════╩════╩══════════╩════╝
注：
1. 按量付费实例 24 小时不启动 /hy-tmp 会被清除
2. 除以上目录外，不要将实例根路径放满，否则将无法正常启动实例
========实例配置========
核数：8
内存：62 GB
磁盘：1% 79M/30G
显卡：NVIDIA GeForce RTX 5060 Ti, 1
root@I28557c0e12011017f0:~# whoami
root
root@I28557c0e12011017f0:~# uname -a
Linux I28557c0e12011017f0 5.15.0-153-generic #163-Ubuntu SMP Thu Aug 7 16:37:18 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux