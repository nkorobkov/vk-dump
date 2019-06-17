## VK-dump 

**UPD: Not supported by VK any more**  
*VK terminated support of their messages API for unauthorized applications from 15th of February 2019. Scripts for message dump presented in this repo relied on that API, and cannot function further*

Yet another GitHub repository with scripts for downloading vk message history. And other stuff.  
 
 Utils would dump all your dialogs with all photo and audio attachments (optional). Present progress bars during wait time and update dumps in seconds.  
 If you don't care about attachments and fast updates consider using vk native tool for data backup <https://vk.com/data_protection?section=rules>


### Installation

After you clone the repo with  
```bash
git clone https://github.com/nkorobkov/vk-dump
```  
You may use virtual environment or just run  

```bash
pip3 install -r requirments.txt
```

to install required libraries and then run script with --help to see available configurations
```bash
python3 vk-msg-dump.py --help
```



