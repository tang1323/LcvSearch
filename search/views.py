from django.shortcuts import render
import json
# 让类Searchsuggest继承Views
from django.views.generic.base import View

from search.models import ArticleType
from elasticsearch import Elasticsearch# 点击搜索
from datetime import datetime
import redis

# 点击搜索的一个连接
client = Elasticsearch(hosts=["127.0.0.1"])

# 连接redis
redis_cli = redis.StrictRedis(host='localhost', port=6379, db=0, charset="utf8", decode_responses=True)

# 将数据返回我们的前端
from django.http import HttpResponse# 将数据返回我们的前端
# Create your views here.


# 这是搜索建议的代码
# 这里尽量用基于类来做，官方文档也是比较建议的
class Searchsuggest(View):
    # 继承之后 就可以重载get这个方法
    def get(self, request):
        key_words = request.GET.get('s', '')
        re_datas = []#搜索建议不止一个，所以创建 一个数组
        if key_words:
            s = ArticleType.search()
            s = s.suggest('my_suggest', key_words, completion={
                "field": "suggest", "fuzzy": {
                    "fuzziness": 2# 编辑距离
                },
                "size": 10
            })
            suggestions = s.execute_suggest()
            for match in suggestions.my_suggest[0].options:
                source = match._source
                re_datas.append(source["title"])# 搜索时返回的一个title回来

        # 将数据返回我们的前端
        return HttpResponse(json.dumps(re_datas), content_type="application/json")


# 点击搜索后出现的列表内容的一个类
class SearchView(View):
    def get(self, requests):
        # 搜索关键词
        key_words = requests.GET.get("q", "")

        # 分页功能
        page = requests.GET.get("p", "1")
        try:
            page = int(page)
        except:
            page = 1

        # 每次进入一条数据redis都做一个加1操作，用来统计有几条数据的
        cnblogs_count = redis_cli.get("cnblogs_count")

        # 查询所需要的时间,这是开始
        start_time = datetime.now()


        response = client.search(
            index="cnblogs",
            body={
                "query": {
                    "multi_match": {
                        "query": key_words,
                        "fields": ["tags", "title", "content"]# 这是要搜索的字段，可以自己加进来
                    }
                },
                # 每页只有10个内容，不能显示过多， 分页就是从第0开始，一页有10个，第二页从第10开始
                "from": (page-1)*10,
                "size": 10,
                # 这个是高亮处理，就是搜索的关键词会变红处理
                "highlight": {
                    # 把自己想要标红的css样式写进来，这个看自己是什么样式
                    "pre_tags": ['<span class="keyWord">'],
                    "post_tags": ['</span>'],

                    "fields": {
                        # 指定哪一个字段做一个高亮处理
                        "title": {},
                        "content": {}
                    }
                }

            }
        )
        # 查询所需要的时间,这是开始
        end_time = datetime.now()
        # 是一个total_seconds()对象
        last_seconds = (end_time - start_time).total_seconds()

        # 有多少条数据
        total_nums = response["hits"]["total"]

        # 计算有几页
        if (page % 10) > 0:
            page_nums = int(total_nums/10) + 1
        else:
            page_nums = int(total_nums/10)

        # 获取数据后，提取想要的值放到一个数组中来，就做一个转换，然后配置到前端去
        hit_list = []
        for hit in response["hits"]["hits"]:
            from collections import defaultdict
            hit_dict = defaultdict(str)
            if "highlight" not in hit:
                hit["highlight"] = {}

            # 先做一个title是否在highlight中，这里是先取出来
            if "title" in hit["highlight"]:
                hit_dict["title"] = "".join(hit["highlight"]["title"])
            else:
                hit_dict["title"] = hit["_source"]["title"]

            # 先做一个content是否在highlight中，这里是先取出来
            if "content" in hit["highlight"]:
                hit_dict["content"] = "".join(hit["highlight"]["content"])[:500]
            # 如果不在highlight中就去_source取
            else:
                hit_dict["content"] = "".join(hit["_source"]["content"])[:500]


            # 时间也要取，但时间一般放在_source下的
            hit_dict["create_date"] = hit["_source"]["create_date"]

            # url也是一样，这个更要取
            hit_dict["url"] = hit["_source"]["url"]
            # 得分
            hit_dict["score"] = hit["_score"]

            # 取完之后就放到一个数组上
            hit_list.append(hit_dict)
        # 然后就返回到 前端去, "all_hits": hit_list是要放到的内容要显示出现，"key_works": key_words重新放在搜索栏中
        return render(requests, "result.html", {"page": page,
                                                "all_hits": hit_list,
                                                "key_words": key_words,
                                                "total_nums": total_nums,
                                                "page_nums": page_nums,
                                                "last_seconds": last_seconds,
                                                "cnblogs_count": cnblogs_count,})



















