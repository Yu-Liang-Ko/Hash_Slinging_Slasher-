from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram.ext import CommandHandler, CallbackQueryHandler  # 指令接收 CallbackQuery
from telegram.ext import PollAnswerHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton  # 互動式按鈕
import random
import json
# 計時
import time
# 文字轉語音
from gtts import gTTS
from os import system

# 文字轉語音輸出 (文字，停留幾秒)
def wordToSpeak(text, sec):
    filename = "speak.mp3"
    tts = gTTS(text=text, lang='zh')
    tts.save(filename)
    # 執行音檔 --- pi 上有 vlc 可直接撥放音檔
    system('cvlc --play-and-exit speak.mp3')
    time.sleep(sec)
    # voice.playMusic(filename)
    # playsound.playsound(filename)


# 最終投票結果
# 玩家投票
def receive_poll_answer(update: Update, context: CallbackContext):
    global players, mode
    answer = update.poll_answer
    poll_id = answer.poll_id
    # 目前總投票人數
    context.bot_data[poll_id]["answers"] += 1
    polled = update.poll_answer.option_ids[0]
    # 該選項投票數
    context.bot_data[poll_id]['result'][polled] += 1
    # Close poll after three participants voted
    if context.bot_data[poll_id]["answers"] == len(players):
        context.bot.stop_poll(
            context.bot_data[poll_id]["chat_id"], context.bot_data[poll_id]["message_id"])
        # 最高票的玩家
        poll_result = context.bot_data[poll_id]['result']
        get_heighest_player = poll_result.index(max(poll_result))+1
        # 如果兩人以上平票 -> 沒人死，遊戲繼續
        poll_result.sort(reverse=True)
        if poll_result[0] == poll_result[1]:
            response = "投票結果為平票，沒有人淘汰，遊戲繼續"
            context.bot.send_message(
                chat_id=context.bot_data[poll_id]["chat_id"], text=response)
        else:
            response = f"投票結果最高票為 {get_heighest_player} 號玩家"
            context.bot.send_message(chat_id=context.bot_data[poll_id]["chat_id"], text=response)
            # 移除淘汰的人
            players.pop(get_heighest_player)
            # 遊戲結束
            checkEnd()
        wordToSpeak("天黑請閉眼", 1)
        process(mode)
# 製作投票
def poll(update: Update, context: CallbackContext):
    global players
    # 投票重置
    option_result = [0 for i in range(len(players))]
    questions = [str(i) for i in players]
    # option_result = [0 for i in range(2)]
    # questions = ["well","good"]
    message = context.bot.send_poll(
        update.effective_chat.id,
        "這局要把誰票出去?",
        questions,
        is_anonymous=False,  # False: 沒有匿名
        allows_multiple_answers=False,  # False:單選
    )
    # Save some info about the poll the bot_data for later use in receive_poll_answer
    payload = {
        message.poll.id: {
            "questions": questions,
            "message_id": message.message_id,
            "chat_id": update.effective_chat.id,
            "answers": 0,
            "result": option_result
        }
    }
    # 開始投票
    updater.start_polling()
    context.bot_data.update(payload)


# 記錄誰死亡 / mode:要被殺還是被救 userID:主導的人 selectNum: 被殺或被救的 userID
def investigation_or_whoPassAway(update, selectNum):
    global whodie, players, mode
    print("investigation_or_whoPassAway", mode)
    # 找到對應的角色的 ID
    # 被狼人殺
    if mode == "werewolf":
        whodie.append(selectNum)
        # 找所有狼人 ID 並發送訊息
        for num in players:
            if players[num]['role'] == mode:
                response = f"您要殺的對象為 {selectNum} 號"
                update.callback_query.edit_message_text(text=response)
    # 預言家
    elif mode == "predictor":
        # 找預言家 ID發送訊息
        for num in players:
            if players[num]['role'] == mode:
                response = f"您查驗的 {selectNum} 號身分是" + \
                    players[selectNum]['role']
                update.callback_query.edit_message_text(text=response)
                return
    # 女巫選擇藥水
    elif mode == "witch":
        print("selectNum", selectNum)
        # mode = selectNum
        # 女巫要毒人
        if selectNum == "poison":
            update.callback_query.edit_message_text(text="您選擇了毒藥")
            keyboard([i for i in players], "poison")
        elif selectNum == "revive":
            mode = "revive"
            # 有人死
            if len(whodie) != 0:
                remaind_bottle[1] = False
                whodie = []
                response = f"您拯救了珍貴的生命"
                update.callback_query.edit_message_text(text=response)
            else:
                response = "哥~沒人死啦!"
                update.callback_query.edit_message_text(text=response)
        # 跳過
        elif selectNum == "skip":
            mode = "skip"
            update.callback_query.edit_message_text(text="您跳過了此回合")
    # 女巫選擇殺誰 selectNum 為玩家號碼
    elif mode == "poison":
        remaind_bottle[0] = False
        if selectNum not in whodie:
            whodie.append(selectNum)
        # 女巫 ID
        for i in players:
            if players[i]['role'] == "witch":
                response = f"您毒死 {selectNum} 號"
                update.callback_query.edit_message_text(text=response)

# 按鈕回應


def reply_button(update: Update, context: CallbackContext):
    global mode
    # string to json
    jsonData = json.loads(update.callback_query.data)
    mode = jsonData['mode']
    selectNum = jsonData['buttonText']
    # 紀錄一下誰死了
    print("reply_button_beforePassway", mode)
    investigation_or_whoPassAway(update, selectNum)
    # update.callback_query.edit_message_text(update.callback_query.data)
    print("reply_button", mode)
    if mode == "werewolf":
        mode = "predictor"
        process(mode)
    elif mode == "predictor":
        mode = "witch"
        process(mode)
    elif mode == "poison":
        mode = "breakingDawn"
        process(mode)
    elif mode == "revive":
        mode = "breakingDawn"
        process(mode)
    elif mode == "skip":
        mode = "breakingDawn"
        process(mode)


# 製作按鈕
def keyboard(buttonList, mode):
    print("keyboard", mode)
    global players
    # InlineBtn.row_width = 2
    keyboard = []
    row = []
    # 顯示僅剩的藥水
    if mode == "witch":
        for i in remaind_bottle:
            if remaind_bottle[i] == False:
                buttonList.pop(i)
    # 回應按鈕
    for btn in buttonList:
        # 對該角色玩家 ID 發送 keyboard
        data = {'mode': mode, 'buttonText': btn}
        # json to string
        dataString = json.dumps(data)
        replyBtn = InlineKeyboardButton(text=btn, callback_data=dataString)
        row.append(replyBtn)
        if buttonList.index(btn) % 3 == 2:
            keyboard.append(row)
            row = []
    if row != []:
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)
    # 傳送 keyboard 給目前符合模式的角色 ID
    # 狼人
    if mode == "werewolf":
        for num in players:
            if players[num]['role'] == mode:
                userID = players[num]['userID']
                updater.bot.send_message(
                    chat_id=userID, text="請選擇獵殺的號碼", reply_markup=reply_markup)
    # 預言家
    elif mode == "predictor":
        for num in players:
            if players[num]['role'] == mode:
                userID = players[num]['userID']
                updater.bot.send_message(
                    chat_id=userID, text="請查驗的號碼", reply_markup=reply_markup)
                return
    # 女巫
    elif mode == "witch":
        for num in players:
            if players[num]['role'] == "witch":
                userID = players[num]['userID']
                updater.bot.send_message(
                    chat_id=userID, text="要使用解藥還是毒藥?", reply_markup=reply_markup)
    elif mode == "poison":
        for num in players:
            if players[num]['role'] == "witch":
                userID = players[num]['userID']
                updater.bot.send_message(
                    chat_id=userID, text="您要毒誰呢?", reply_markup=reply_markup)
    # updater.bot.send_chat_action(updater.message.chat.id, 'typing')

# 各個模式
def process(step):
    print("process-step", mode)
    # 狼人模式

    def wolf():
        updater.bot.send_message(chat_id=group_id, text=f"狼人請睜眼")
        system('cvlc --play-and-exit '+mode+'.mp3')
        # path = "./"+step+".mp3"
        # playsound.playsound(path)
        wordToSpeak("狼人請睜眼", 1)
        # 狼人請殺人(10 sec)
        wordToSpeak("狼人請殺人", 1)
        # 跳出 keyboard 選擇號碼 --- 一個人負責點選殺誰
        keyboard([i for i in players], "werewolf")
    # 預言家模式

    def predict():
        global players, mode
        # path = "./"+step+".mp3"
        # playsound.playsound(path)
        live = False
        for i in players:
            if players[i]['role'] == mode:
                live = True
                break
        wordToSpeak("狼人請閉眼", 1)
        updater.bot.send_message(chat_id=group_id, text=f"預言家請睜眼")
        system('cvlc --play-and-exit '+mode+'.mp3')
        wordToSpeak("預言家請睜眼", 1)
        wordToSpeak("預言家請選擇要查驗的對象", 1)
        keyboard([i for i in players], "predictor")
        # 預言家死了
        if live == False:
            mode = "witch"
            process(mode)
    # 女巫模式

    def witch():
        # path = "./"+step+".mp3"
        # playsound.playsound(path)
        global players, mode
        updater.bot.send_message(chat_id=group_id, text=f"女巫請睜眼")
        live = False
        for i in players:
            if players[i]['role'] == mode:
                live = True
                break
        wordToSpeak("預言家請閉眼", 1)
        system('cvlc --play-and-exit '+mode+'.mp3')
        wordToSpeak("女巫請睜眼", 1)
        wordToSpeak("有人被殺了，請問要救他嗎?還是要使用毒藥呢?", 1)
        keyboard(["poison", "revive", "skip"], "witch")
        # 女巫死了
        if live == False:
            mode = "breakingDawn"
            process(mode)
    # 天亮模式

    def breakingDawn():
        global players, mode, group_id,whodie

        wordToSpeak("女巫請閉眼", 1)
        # 天亮了 --- 誰死了 or 平安夜
        # 沒有人死
        system('cvlc --play-and-exit '+mode+'.mp3')
        if len(whodie) == 0:
            updater.bot.send_message(chat_id=group_id, text=f"天亮了!今晚是平安夜")
            wordToSpeak(f"天亮了!今晚是平安夜", 1)
        # 有人死亡
        else:
            whodie.sort()
            number = [str(i)+"號" for i in whodie]
            updater.bot.send_message(chat_id=group_id, text=f"天亮了! {number} 死了")
            wordToSpeak(f"天亮了! {number} 死了", 1)
            # 移除死亡的人
            for i in whodie:
                del players[i]
            whodie = []
        # 遊戲結束
        checkEnd()
        mode = "werewolf"
    if status == True:
        if step == "werewolf":
            wolf()
        elif step == "predictor":
            predict()
        elif step == "witch":
            witch()
        elif step == "breakingDawn":
            breakingDawn()

# 檢查遊戲是否結束
def checkEnd():
    global players, status, group_id
    woo = 0  # 狼人
    mortal = 0  # 平民
    for i in players:
        if players[i]['role'] == "werewolf":
            woo += 1
        elif players[i]['role'] == "civilian":
            mortal += 1
    # 遊戲結束
    # 狼人全死
    if woo == 0:
        clearData()
        wordToSpeak("遊戲結束，好人獲勝!", 1)
        updater.bot.send_message(chat_id=group_id, text="遊戲結束 ! 好人獲勝")
    # 平民全死
    elif mortal == 0:
        clearData()
        wordToSpeak("遊戲結束，狼人獲勝!", 1)
        updater.bot.send_message(chat_id=group_id, text="遊戲結束! 狼人獲勝")

# 角色分配
def distribution(players, playerNum):
    playerRole = dict()
    number = len(players)
    roles = ['werewolf', 'witch', 'predictor', 'civilian']
    # 遊玩人數至少 4 人,以  人為基準分配角色 （神職固定 2 人）
    differ = number - 4
    if differ == 0:
        pass
    # 偶數 狼人比平民多一點
    elif (differ)%2 == 0:
        for i in range(differ//2):
            roles.append("werewolf")
        for i in range(differ//2):
            roles.append("civilian")
    # 奇數 平民比狼人多一點
    else:
        for i in range(differ//2):
            roles.append("werewolf")
        for i in range(differ-differ//2):
            roles.append("civilian")
    random.shuffle(roles)
    for i in range(playerNum):
        data = dict()
        data['userID'] = players[i]['userID']
        data['role'] = roles[i]
        data['name'] = players[i]['name']
        playerRole[i+1] = data
    return playerRole

# 遊戲開始
def start(update: Update, context: CallbackContext):
    global players, status, mode, group_id, remaind_bottle
    # 女巫藥水
    remaind_bottle = [True for i in range(3)]
    # 紀錄當天夜晚死亡號碼
    whodie = []
    # 遊玩人數至少要 4 個
    if len(players) >= 4:
        # 遊戲已經進行
        if status == True:
            response = "遊戲已進行，若要重新開始請先結束遊戲!"
            update.message.reply_text(response)
            return
        status = True
        # 各個玩家資訊(編號、userID、角色、telegram's 名字)/角色分配
        playerRole = distribution(players, len(players))
        # 對群組/玩家發送通知
        response = "遊戲開始"
        updater.bot.send_message(chat_id=group_id, text=response)
        for players in range(len(playerRole)):
            userID = playerRole[players+1]['userID']
            role = playerRole[players+1]['role']
            text = f"您是{players+1}號,角色是:{role}"
            updater.bot.send_message(chat_id=userID, text=text)
        players = playerRole
        wordToSpeak("遊戲開始 5 秒後進入傍晚，請至私人聊天室確認自己的號碼和身分",1)
        wordToSpeak("倒數 5 秒", 1)
        for i in range(4, 0, -1):
            wordToSpeak(str(i), 1)
        wordToSpeak("天黑請閉眼", 1)
        process(mode)
    else:
        updater.bot.send_message(
            chat_id=update.message.chat_id, text="人數不足 4 人，無法進行遊戲")

# 清除資料
def clearData():
    # 記錄清空
    global players, status, group_id
    players = []
    status = False

# 遊戲中止
def stop(update: Update, context: CallbackContext):
    clearData()
    response = "遊戲結束"
    updater.bot.send_message(chat_id=group_id, text=response)

# 取消準備
def cancel(update: Update, context: CallbackContext):
    global group_id
    userID = update.message.from_user.id
    # 檢查有沒有準備中
    if userID in players:
        players.remove(update.message.from_user.id)
        response = f"已取消準備\n目前準備人數 {len(players)} 人"
    else:
        response = "您並未準備"
    updater.bot.send_message(chat_id=group_id, text=response)

# 玩家準備 --- 同時記錄 ID & 人數
def prepare(update: Update, context: CallbackContext):

    # 只有群組才可以準備
    if update.message.chat_id >= 0:
        updater.bot.send_message(
            chat_id=update.message.chat_id, text="狼人殺只可以在群組內玩~")
        return
    global players, group_id
    userID = update.message.from_user.id
    group_id = update.message.chat_id
    name = update.effective_user.full_name  # 玩家本名 -- 陳XX
    hasPrepare = False  # 是否準備過
    response = ""
    # 之前未準備過
    for data in players:
        if str(userID) == str(data['userID']):
            hasPrepare = True
            response = "您已準備完成!"
            break
    if hasPrepare == False:
        userData = dict()
        userData['userID'] = userID
        userData['name'] = name
        players.append(userData)
        response = f"目前準備人數 {len(players)} 人"
    updater.bot.send_message(chat_id=group_id, text=response)

# 列出目前所有準備的玩家


def listPrepare(update: Update, context: CallbackContext):
    global players
    response = ""
    for i in players:
        response += f"號"
        response += players[i]['name']
        response += "\n"
    response += f"以上總共 {len(players)} 位玩家已準備"
    updater.bot.send_message(chat_id=update.message.chat_id, text=response)

# 介紹文
def introduce(update: Update, context: CallbackContext):
    response = '主持人可以透過 telegram bot 下指令，調整燈光\n' +\
               '/start 遊戲開始後，有流程指令可以下達，且可隨意終止遊戲\n' +\
               '/color (看看可不可以隨意調燈光顏色)(調狼人殺燈光或是不玩遊戲單純調燈光顏色)'
    update.message.reply_text(response)


def command():
    updater.dispatcher.add_handler(CommandHandler('introduce', introduce))
    updater.dispatcher.add_handler(CommandHandler('listprepare', listPrepare))
    updater.dispatcher.add_handler(CommandHandler('prepare', prepare))
    updater.dispatcher.add_handler(CommandHandler('cancel', cancel))
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(CallbackQueryHandler(reply_button))
    updater.dispatcher.add_handler(CommandHandler('poll', poll))
    updater.dispatcher.add_handler(PollAnswerHandler(receive_poll_answer))


players = []  # 玩家資訊
status = False  # 遊戲使否進行中
mode = "werewolf"  # 現在遊戲的模式
group_id = 0  # 群組 ID
remaind_bottle = [True for i in range(3)]  # 各藥水是否還有 True:還有藥水
whodie = [] # 紀錄這個晚上誰死了

if __name__ == "__main__":
    file = open("token.txt", mode='r')
    token = file.read().strip()
    updater = Updater(token)
    command()
    updater.start_polling()
    updater.idle()