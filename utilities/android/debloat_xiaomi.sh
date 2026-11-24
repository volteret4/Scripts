#!/usr/bin/env bash
#
#   Desinstala del $dispositivo los siguientes programas
#   Busca el id con `adb devices`
#

dispositivo="653ffbad"

adb -s "${dispositivo}" shell cmd package install-existing android.autoinstalls.config.Xiaomi.ginkgo
adb -s "${dispositivo}" shell cmd package install-existing cn.wps.moffice_eng
adb -s "${dispositivo}" shell cmd package install-existing cn.wps.xiaomi.abroad.lite
adb -s "${dispositivo}" shell cmd package install-existing com.alibaba.aliexpresshd
adb -s "${dispositivo}" shell cmd package install-existing com.allgoritm.youla
adb -s "${dispositivo}" shell cmd package install-existing com.amazon.mShop.android.shopping
adb -s "${dispositivo}" shell cmd package install-existing com.android.bookmarkprovider
adb -s "${dispositivo}" shell cmd package install-existing com.android.browser
adb -s "${dispositivo}" shell cmd package install-existing com.android.chrome
adb -s "${dispositivo}" shell cmd package install-existing com.android.fmradio
adb -s "${dispositivo}" shell cmd package install-existing com.android.hotwordenrollment.okgoogle
adb -s "${dispositivo}" shell cmd package install-existing com.android.hotwordenrollment.xgoogle
adb -s "${dispositivo}" shell cmd package install-existing com.android.providers.downloads.ui
adb -s "${dispositivo}" shell cmd package install-existing com.android.soundrecorder
adb -s "${dispositivo}" shell cmd package install-existing com.android.stk
adb -s "${dispositivo}" shell cmd package install-existing com.android.wallpaper.livepicker
adb -s "${dispositivo}" shell cmd package install-existing com.block.puzzle.game.hippo.mi
adb -s "${dispositivo}" shell cmd package install-existing com.booking
adb -s "${dispositivo}" shell cmd package install-existing com.crazy.juicer.xm
adb -s "${dispositivo}" shell cmd package install-existing com.duokan.phone.remotecontroller
adb -s "${dispositivo}" shell cmd package install-existing com.ebay.carrier
adb -s "${dispositivo}" shell cmd package install-existing com.ebay.mobile
adb -s "${dispositivo}" shell cmd package install-existing com.facemoji.lite.xiaomi
adb -s "${dispositivo}" shell cmd package install-existing com.facebook.appmanager
adb -s "${dispositivo}" shell cmd package install-existing com.facebook.katana
adb -s "${dispositivo}" shell cmd package install-existing com.facebook.services
adb -s "${dispositivo}" shell cmd package install-existing com.facebook.system
adb -s "${dispositivo}" shell cmd package install-existing com.google.ambient.streaming
adb -s "${dispositivo}" shell cmd package install-existing com.google.ar.core
adb -s "${dispositivo}" shell cmd package install-existing com.google.ar.lens
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.adm
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.docs
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.googleassistant
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.healthdata
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.magazines
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.maps
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.nbu.files
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.photos
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.podcasts
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.safetyhub
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.subscriptions.red
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.tachyon
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.turbo
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.walletnfcrel
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.apps.youtube.music
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.calendar
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.feedback
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.gm
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.googlequicksearchbox
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.healthconnect.controller
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.inputmethod.latin
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.marvin.talkback
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.mms
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.music
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.play.games
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.projection.gearhead
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.talk
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.videos
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.youtube
adb -s "${dispositivo}" shell cmd package install-existing com.igg.android.lordsmobile
adb -s "${dispositivo}" shell cmd package install-existing com.iflytek.inputmethod.miui
adb -s "${dispositivo}" shell cmd package install-existing com.jewelsblast.ivygames.Adventure.free
adb -s "${dispositivo}" shell cmd package install-existing com.kingsgroup.ss.xiaomi
adb -s "${dispositivo}" shell cmd package install-existing com.kms.free
adb -s "${dispositivo}" shell cmd package install-existing com.linkedin.android
adb -s "${dispositivo}" shell cmd package install-existing com.logame.eliminateintruder3d
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.global.bbs
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.global.pocobbs
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.global.pocostore
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.global.shop
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.health
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.liveassistant
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.mishare.connectivity
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.android.globalFileexplorer
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.android.globalminusscreen
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.globalbrowser
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.pay.wallet.id
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.pay.wallet.in
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.analytics
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.android.fashiongallery
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.bugreport
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.cleaner
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.cleanmaster
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.compass
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.cloudservice
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.daemon
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.fm
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.fmservice
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.global.packageinstaller
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.huanji
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.hybrid
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.hybrid.accessory
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.miservice
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.msa.global
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.newmidrive
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.notes
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.player
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.smarttravel
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.translation.kingsoft
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.translation.xmcloud
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.translation.youdao
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.translationservice
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.userguide
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.videoplayer
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.voiceassist
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.weather2
# adb -s "${dispositivo}" shell cmd package install-existing com.mi.ui.yellowpage
# adb -s "${dispositivo}" shell cmd package install-existing com.micredit.in
# adb -s "${dispositivo}" shell cmd package install-existing com.micredit.in.gp
# adb -s "${dispositivo}" shell cmd package install-existing com.mintgames.triplecrush.tile.fun
# adb -s "${dispositivo}" shell cmd package install-existing com.mintgames.wordtrip
# adb -s "${dispositivo}" shell cmd package install-existing com.mipay.wallet.id
# adb -s "${dispositivo}" shell cmd package install-existing com.mipay.wallet.in
adb -s "${dispositivo}" shell cmd package install-existing com.mobilelegends.mi
adb -s "${dispositivo}" shell cmd package install-existing com.netflix.mediaclient
adb -s "${dispositivo}" shell cmd package install-existing com.netflix.partner.activation
adb -s "${dispositivo}" shell cmd package install-existing com.nf.snake
adb -s "${dispositivo}" shell cmd package install-existing com.opera.browser
adb -s "${dispositivo}" shell cmd package install-existing com.opera.preinstall
adb -s "${dispositivo}" shell cmd package install-existing com.preff.kb.xm
adb -s "${dispositivo}" shell cmd package install-existing com.sohu.inputmethod.sogou.xiaomi
adb -s "${dispositivo}" shell cmd package install-existing com.spotify.music
adb -s "${dispositivo}" shell cmd package install-existing com.sukhavati.gotoplaying.bubble.BubbleShooter.mint
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.aicr
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.discover
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.glgm
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.joyose
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.mibrain.speech
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.midrop
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.mipicks
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.mirecycle
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.payment
# adb -s "${dispositivo}" shell cmd package install-existing com.xiaomi.smarthome
adb -s "${dispositivo}" shell cmd package install-existing com.yandex.browser
adb -s "${dispositivo}" shell cmd package install-existing com.yandex.preinstallsatellite
adb -s "${dispositivo}" shell cmd package install-existing com.yandex.searchplugin
adb -s "${dispositivo}" shell cmd package install-existing com.yandex.zen
adb -s "${dispositivo}" shell cmd package install-existing com.yandex.zenkitpartnerconfig
adb -s "${dispositivo}" shell cmd package install-existing com.zhiliaoapp.musically
adb -s "${dispositivo}" shell cmd package install-existing ru.aliexpress.buyer
adb -s "${dispositivo}" shell cmd package install-existing ru.ivi.client
adb -s "${dispositivo}" shell cmd package install-existing ru.ozon.app.android
adb -s "${dispositivo}" shell cmd package install-existing ru.vk.store
adb -s "${dispositivo}" shell cmd package install-existing ru.yandex.searchplugin

adb -s "${dispositivo}" shell cmd package install-existing com.android.vending
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.gms
adb -s "${dispositivo}" shell cmd package install-existing com.google.android.gsf
