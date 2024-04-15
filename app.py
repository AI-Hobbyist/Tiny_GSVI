

from datetime import datetime
import gradio as gr
import json, os
import requests
import numpy as np
from string import Template
import  wave

# 在开头加入路径
import os, sys
now_dir = os.getcwd()
sys.path.append(now_dir)

# 尝试清空含有GPT_SoVITS的路径
for path in sys.path:
    if path.find(r"GPT_SoVITS") != -1:
        sys.path.remove(path)
        
# 取得模型文件夹路径
from src.config_manager import Inference_Config
from src.config_manager import __version__ as frontend_version
inference_config = Inference_Config()
default_word_count = inference_config.default_word_count
max_text_length = inference_config.max_text_length

from tools.i18n.i18n import I18nAuto
i18n = I18nAuto(locale_path="i18n/locale")

import nltk
nltk.data.path.append(os.path.abspath(os.path.join(now_dir,"nltk_data")))


language_list = ["auto", "zh", "en", "ja", "all_zh", "all_ja"]
translated_language_list = [i18n("auto"), i18n("zh"), i18n("en"), i18n("ja"), i18n("all_zh"), i18n("all_ja")] # 由于i18n库的特性，这里需要全部手输一遍
language_dict = dict(zip(translated_language_list, language_list))

cut_method_list = ["auto_cut", "cut0", "cut1", "cut2", "cut3", "cut4", "cut5"]
translated_cut_method_list = [i18n("auto_cut"), i18n("cut0"), i18n("cut1"), i18n("cut2"), i18n("cut3"), i18n("cut4"), i18n("cut5")]
cut_method_dict = dict(zip(translated_cut_method_list, cut_method_list))



def load_character_emotions(character_name, characters_and_emotions):
    emotion_options = ["default"]
    emotion_options = characters_and_emotions.get(character_name, ["default"])

    return gr.Dropdown(emotion_options, value="default")



from Adapters.gsv_fast import GSV_Instance as TTS_instance
tts_instance = TTS_instance()

import soundfile as sf


def get_audio(
    text,
    cha_name,
    text_language,
    batch_size,
    speed_factor,
    top_k,
    top_p,
    temperature,
    character_emotion,
    cut_method,
    word_count,
    seed,
    stream="False",
):

    text_language = language_dict[text_language]
    cut_method = cut_method_dict[cut_method]
    if cut_method == "auto_cut":
        cut_method = f"{cut_method}_{word_count}"
    # Using Template to fill in variables
    
    

    stream = stream.lower() in ('true', '1', 't', 'y', 'yes')
    
    
    params = {
        "text": text,
        "text_language": text_language,
        
        "character": cha_name,
        "emotion": character_emotion,
        "top_k": top_k,
        "top_p": top_p,
        "temperature": temperature,
        "cut_method": cut_method,
        "stream": stream,
        "seed": seed,
        "speed_factor": speed_factor,
        "batch_size": batch_size,
    }
    # 如果不是经典模式，则添加额外的参数
    
    
    try:
        task = tts_instance.params_analyser(params)
        gen = tts_instance.generate(task)
        sampling_rate, audio_data = next(gen)
    except Exception as e:
        gr.Warning(f"Error: {e}")

    return sampling_rate, np.array(audio_data,dtype=np.int16)
    

def stopAudioPlay():
    return


global characters_and_emotions_dict
characters_and_emotions_dict = {}

def get_characters_and_emotions():
    global characters_and_emotions_dict
    # 直接检查字典是否为空，如果不是，直接返回，避免重复获取
    if characters_and_emotions_dict == {}:
        characters_and_emotions_dict = tts_instance.get_characters()
        print(characters_and_emotions_dict)
   
    return characters_and_emotions_dict
  
def change_character_list(
    cha_name="", auto_emotion=False, character_emotion="default"
):

    characters_and_emotions = {}

    try:
        characters_and_emotions = get_characters_and_emotions()
        character_names = [i for i in characters_and_emotions]
        if len(character_names) != 0:
            if cha_name in character_names:
                character_name_value = cha_name
            else:
                character_name_value = character_names[0]
        else:
            character_name_value = ""
        emotions = characters_and_emotions.get(character_name_value, ["default"])
        emotion_value = character_emotion
        if auto_emotion == False and emotion_value not in emotions:
            emotion_value = "default"
    except:
        character_names = []
        character_name_value = ""
        emotions = ["default"]
        emotion_value = "default"
        characters_and_emotions = {}
    if auto_emotion:
        return (
            gr.Dropdown(character_names, value=character_name_value, label=i18n("选择角色")),
            gr.Checkbox(auto_emotion, label=i18n("是否自动匹配情感"), visible=False, interactive=False),
            gr.Dropdown(["auto"], value="auto", label=i18n("情感列表"), interactive=False),
            characters_and_emotions,
        )
    return (
        gr.Dropdown(character_names, value=character_name_value, label=i18n("选择角色")),
        gr.Checkbox(auto_emotion, label=i18n("是否自动匹配情感"),visible=False, interactive=False),
        gr.Dropdown(emotions, value=emotion_value, label=i18n("情感列表"), interactive=True),
        characters_and_emotions,
    )


def change_endpoint(url):
    url = url.strip()
    return gr.Textbox(f"{url}/tts"), gr.Textbox(f"{url}/character_list")




def cut_sentence_multilang(text, max_length=30):
    if max_length == -1:
        return text, ""
    # 初始化计数器
    word_count = 0
    in_word = False
    
    
    for index, char in enumerate(text):
        if char.isspace():  # 如果当前字符是空格
            in_word = False
        elif char.isascii() and not in_word:  # 如果是ASCII字符（英文）并且不在单词内
            word_count += 1  # 新的英文单词
            in_word = True
        elif not char.isascii():  # 如果字符非英文
            word_count += 1  # 每个非英文字符单独计为一个字
        if word_count > max_length:
            return text[:index], text[index:]
    
    return text, ""


default_text = i18n("我是一个粉刷匠，粉刷本领强。我要把那新房子，刷得更漂亮。刷了房顶又刷墙，刷子像飞一样。哎呀我的小鼻子，变呀变了样。")

if "。" not in default_text:
    _sentence_list = default_text.split(".")
    default_text = ".".join(_sentence_list[:1]) + "."
else:
    _sentence_list = default_text.split("。")
    default_text = "。".join(_sentence_list[:2]) + "。"

information = ""

try:
    with open("Information.md", "r", encoding="utf-8") as f:
        information = f.read()
except:
    pass


with gr.Blocks() as app:
    gr.Markdown(information)
    with gr.Row():
        max_text_length_tip = "" if max_text_length == -1 else f"( "+i18n("最大允许长度")+ f" : {max_text_length} ) "
        text = gr.Textbox(
            value=default_text, label=i18n("输入文本")+max_text_length_tip, interactive=True, lines=8
        )
        text.blur(lambda x: gr.update(value=cut_sentence_multilang(x,max_length=max_text_length)[0]), [text], [text])
    with gr.Row():
        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab(label=i18n("基础选项")):
                    with gr.Group():
                        text_language = gr.Dropdown(
                            translated_language_list,
                            value=translated_language_list[0],
                            label=i18n("文本语言"),
                        )
                        
                    with gr.Group():
                        (
                            cha_name,
                            auto_emotion_checkbox,
                            character_emotion,
                            characters_and_emotions_,
                        ) = change_character_list()
                        characters_and_emotions = gr.State(characters_and_emotions_)
                        scan_character_list = gr.Button(i18n("扫描人物列表"), variant="secondary")

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab(label=i18n("基础选项")):
                    
                    with gr.Group():
                        speed_factor = gr.Slider(
                            minimum=0.25,
                            maximum=4,
                            value=1,
                            label=i18n("语速"),
                            step=0.05,
                            
                        )
                    with gr.Group():

                        cut_method = gr.Dropdown(
                            translated_cut_method_list,
                            value=translated_cut_method_list[0],
                            label=i18n("切句方式"),
                            
                        )
                        batch_size = gr.Slider(
                            minimum=1,
                            maximum=35,
                            value=10,
                            label=i18n("batch_size，1代表不并行，越大越快，但是越可能出问题"),
                            step=1,
                            
                        )
                        word_count = gr.Slider(
                            minimum=5,maximum=500,value=default_word_count,label=i18n("每句允许最大切分字词数"),step=1, 
                        )

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.Tab(label=i18n("高级选项")):


                    with gr.Group():
                        seed = gr.Number(
                            -1,
                            label=i18n("种子"),
                            
                            interactive=True,
                        )
                    
   
                    with gr.Group():
                        top_k = gr.Slider(minimum=1, maximum=30, value=3, label=i18n("Top K"), step=1)
                        top_p = gr.Slider(minimum=0, maximum=1, value=0.8, label=i18n("Top P"))
                        temperature = gr.Slider(
                            minimum=0, maximum=1, value=0.8, label=i18n("Temperature")
                        )
            cut_method.input(lambda x: gr.update(visible=(cut_method_dict[x]=="auto_cut")),  [cut_method], [word_count])
    with gr.Tabs():
        with gr.Tab(label=i18n("请求完整音频")):
            with gr.Row():
                sendRequest = gr.Button(i18n("发送请求"), variant="primary")
                audioRecieve = gr.Audio(
                    None, label=i18n("音频输出"), type="filepath", streaming=False
                )
        with gr.Tab(label=i18n("流式音频"),interactive=False,visible=False):
            with gr.Row():
                sendStreamRequest = gr.Button(
                    i18n("发送并开始播放"), variant="primary", interactive=True
                )
                stopStreamButton = gr.Button(i18n("停止播放"), variant="secondary")
            with gr.Row():
                audioStreamRecieve = gr.Audio(None, label=i18n("音频输出"), interactive=False)
    gr.HTML("<hr style='border-top: 1px solid #ccc; margin: 20px 0;' />")
    gr.HTML(
        f"""<p>{i18n("这是一个由")} <a href="{i18n("https://space.bilibili.com/66633770")}">XTer</a> {i18n("提供的推理特化包，当前版本：")}<a href="https://www.yuque.com/xter/zibxlp/awo29n8m6e6soru9">{frontend_version}</a>  {i18n("项目开源地址：")} <a href="https://github.com/X-T-E-R/TTS-for-GPT-soVITS">Github</a></p>
            <p>{i18n("吞字漏字属于正常现象，太严重可尝试换行、加句号或调节batch size滑条。")}</p>
            <p>{i18n("若有疑问或需要进一步了解，可参考文档：")}<a href="{i18n("https://www.yuque.com/xter/zibxlp")}">{i18n("点击查看详细文档")}</a>。</p>"""
    )
    # 以下是事件绑定
    app.load(
        change_character_list,
        inputs=[cha_name, auto_emotion_checkbox, character_emotion],
        outputs=[
            cha_name,
            auto_emotion_checkbox,
            character_emotion,
            characters_and_emotions,
        ]
    )            
    sendRequest.click(lambda: gr.update(interactive=False), None, [sendRequest]).then(
        get_audio,
        inputs=[
            text,
            cha_name,
            text_language,
            batch_size,
            speed_factor,
            top_k,
            top_p,
            temperature,
            character_emotion,
            cut_method,
            word_count,
            seed,
            gr.State("False"),
        ],
        outputs=[audioRecieve],
    ).then(lambda: gr.update(interactive=True), None, [sendRequest])
    sendStreamRequest.click(
        lambda: gr.update(interactive=False), None, [sendStreamRequest]
    ).then(
        get_audio,
        inputs=[
            text,
            cha_name,
            text_language,
            batch_size,
            speed_factor,
            top_k,
            top_p,
            temperature,
            character_emotion,
            cut_method,
            word_count,
            seed,
            gr.State("True"),
        ],
        outputs=[audioStreamRecieve],
    ).then(
        lambda: gr.update(interactive=True), None, [sendStreamRequest]
    )
    stopStreamButton.click(stopAudioPlay, inputs=[])
    cha_name.change(
        load_character_emotions,
        inputs=[cha_name, characters_and_emotions],
        outputs=[character_emotion],
    )
    
    scan_character_list.click(
        change_character_list,
        inputs=[cha_name, auto_emotion_checkbox, character_emotion],
        outputs=[
            cha_name,
            auto_emotion_checkbox,
            character_emotion,
            characters_and_emotions,
        ],
    )
    auto_emotion_checkbox.input(
        change_character_list,
        inputs=[cha_name, auto_emotion_checkbox, character_emotion],
        outputs=[
            cha_name,
            auto_emotion_checkbox,
            character_emotion,
            characters_and_emotions,
        ],
    )

is_share = inference_config.is_share
app.queue().launch(show_error=True, share=is_share, inbrowser=True)

