### 1、 创建虚拟环境
```
conda create --name umlagent python=3.11
conda activate umlagent
```
### 2、clone 项目, 切换到分支 magent
```
git clone git@github.com:fujiwarazz/umlagent.git

git checkout magent
```

### 3、下载依赖以及graphviz
```
pip install -r requirements.txt
```
进入 https://www.graphviz.org/download/  下载
然后打开cmd，运行 dot --version 查看是否下载成功
### 4、修改config.yml,改成自己的dashscope的api key

### 5、（optional）运行 /app/examples下的例子

### 5、运行后端
```
uvicorn main:app
```
### 6、运行前端
  进入script目录，使用live server运行webui.html（可能有bug）或者在本地直接打开webui.html
