"""
Email Domain Validation Utility

Blocks disposable/temporary email domains to prevent abuse.
Users trying to create accounts with these domains will be asked
to use a real email address.
"""
import re
import logging

logger = logging.getLogger(__name__)

# Comprehensive list of disposable email domains
# Sources: https://github.com/disposable-email-domains/disposable-email-domains
DISPOSABLE_EMAIL_DOMAINS = {
    # Most common disposable email services
    '10minutemail.com', '10minutemail.net', '10minutemail.org',
    '20minutemail.com', '20minutemail.it',
    'tempmail.com', 'tempmail.net', 'temp-mail.org', 'temp-mail.io',
    'guerrillamail.com', 'guerrillamail.org', 'guerrillamail.net', 'guerrillamail.biz',
    'guerrillamail.de', 'grr.la', 'sharklasers.com', 'guerrillamailblock.com',
    'mailinator.com', 'mailinator.net', 'mailinator.org', 'mailinator2.com',
    'throwaway.email', 'throwawaymail.com',
    'fakeinbox.com', 'fakemailgenerator.com',
    'getnada.com', 'tempail.com', 'tempr.email',
    'dispostable.com', 'mailnesia.com', 'spamgourmet.com',
    'mytrashmail.com', 'mt2009.com', 'trashmail.com', 'trashmail.net',
    
    # Yopmail and variants
    'yopmail.com', 'yopmail.fr', 'yopmail.net', 'cool.fr.nf', 'jetable.fr.nf',
    'courriel.fr.nf', 'moncourrier.fr.nf', 'speed.1s.fr', 'nospam.ze.tc',
    
    # Temp mail services
    'tempinbox.com', 'tempmailaddress.com', 'tempmails.org',
    'tmpmail.org', 'tmpmail.net', 'tm.com',
    
    # Burner mail services
    'burnermail.io', 'burnermailprovider.com',
    
    # Maildrop
    'maildrop.cc', 'mailsac.com',
    
    # Mohmal
    'mohmal.com', 'mohmal.im', 'mohmal.in', 'mohmal.tech',
    
    # Other common ones
    'mailcatch.com', 'mailnull.com', 'spamex.com',
    'emailondeck.com', 'fakeinbox.net', 'inboxkitten.com',
    'getairmail.com', 'discard.email', 'discardmail.com',
    'spamfree24.org', 'spamfree24.de', 'spamfree24.eu',
    'mintemail.com', 'spamobox.com', 'dumpmail.de',
    'wegwerfmail.de', 'wegwerfmail.net', 'wegwerfmail.org',
    'sofort-mail.de', 'sofortmail.de', 'einrot.com',
    'trash-mail.com', 'trash-mail.de', 'trashmail.ws',
    'mailexpire.com', 'mailmoat.com', 'mailnator.com',
    'mailscrap.com', 'mailslite.com', 'mailzilla.com',
    'meltmail.com', 'mvrht.net', 'nervmich.net',
    'nobulk.com', 'nobuma.com', 'nomail.xl.cx',
    'nomail2me.com', 'nomorespamemails.com', 'nospam.ws',
    'nospam4.us', 'nospamfor.us', 'nospammail.net',
    'notmailinator.com', 'nowmymail.com', 'obobbo.com',
    'oneoffemail.com', 'onewaymail.com', 'oopi.org',
    'ordinaryamerican.net', 'owlpic.com', 'pjjkp.com',
    'politikerclub.de', 'poofy.org', 'pookmail.com',
    'privacy.net', 'privatdemail.net', 'proxymail.eu',
    'prtnx.com', 'putthisinyourspamdatabase.com',
    'quickinbox.com', 'rcpt.at', 'receiveee.com',
    'regbypass.com', 'regbypass.comsafe-mail.net',
    'rejectmail.com', 'remail.cf', 'rhyta.com',
    'rklips.com', 'rmqkr.net', 's0ny.net',
    'safe-mail.net', 'safersignup.de', 'safetymail.info',
    'safetypost.de', 'sandelf.de', 'saynotospams.com',
    'selfdestructingmail.com', 'sendspamhere.com',
    'sharedmailbox.org', 'shieldemail.com', 'shiftmail.com',
    'shitmail.me', 'shortmail.net', 'shut.name', 'shut.ws',
    'sibmail.com', 'sinnlos-mail.de', 'siteposter.net',
    'skeefmail.com', 'slaskpost.se', 'slave-auctions.net',
    'slopsbox.com', 'smashmail.de', 'smellfear.com',
    'snakemail.com', 'sneakemail.com', 'snkmail.com',
    'sofimail.com', 'sogetthis.com', 'sohu.com',
    'solvemail.info', 'soodonims.com', 'spam.la',
    'spam.su', 'spam4.me', 'spamail.de', 'spamarrest.com',
    'spamavert.com', 'spambob.com', 'spambob.net',
    'spambob.org', 'spambog.com', 'spambog.de',
    'spambog.ru', 'spambox.info', 'spambox.irishspringrealty.com',
    'spambox.us', 'spamcannon.com', 'spamcannon.net',
    'spamcero.com', 'spamcon.org', 'spamcorptastic.com',
    'spamcowboy.com', 'spamcowboy.net', 'spamcowboy.org',
    'spamday.com', 'spameater.com', 'spameater.org',
    'spamfighter.cf', 'spamfighter.ga', 'spamfighter.gq',
    'spamfighter.ml', 'spamfighter.tk', 'spamfree.eu',
    'spamfree24.com', 'spamfree24.info', 'spamfree24.net',
    
    # Mailchimp test domains
    'mailchimp.com',
    
    # Additional services
    'crazymailing.com', 'crazy.com', 'deadaddress.com',
    'despam.it', 'despammed.com', 'devnullmail.com',
    'dfgh.net', 'digitalsanctuary.com', 'dingbone.com',
    'discard.email', 'discardmail.com', 'discardmail.de',
    'disposable.com', 'disposableaddress.com', 'disposableemailaddresses.com',
    'disposableinbox.com', 'dispose.it', 'disposeamail.com',
    'disposemail.com', 'dispomail.eu', 'dm.w3internet.co.uk',
    'dodgeit.com', 'dodgit.com', 'dodgit.org',
    'donemail.ru', 'dontreg.com', 'dontsendmespam.de',
    'drdrb.com', 'dump-email.info', 'dumpandjunk.com',
    'dumpyemail.com', 'e-mail.com', 'e-mail.org',
    'e4ward.com', 'easytrashmail.com', 'einmalmail.de',
    'email60.com', 'emailigo.de', 'emailinfive.com',
    'emaillime.com', 'emailmiser.com', 'emailsensei.com',
    'emailtemporanea.com', 'emailtemporanea.net', 'emailtemporar.ro',
    'emailtemporario.com.br', 'emailthe.net', 'emailtmp.com',
    'emailto.de', 'emailwarden.com', 'emailx.at.hm',
    'emailxfer.com', 'emz.net', 'enterto.com',
    'ephemail.net', 'etranquil.com', 'etranquil.net',
    'etranquil.org', 'evopo.com', 'example.com',
    'explodemail.com', 'express.net.ua', 'eyepaste.com',
    'fakeinbox.cf', 'fakeinbox.ga', 'fakeinbox.gq',
    'fakeinbox.ml', 'fakeinbox.tk', 'fakemail.fr',
    'fakemailz.com', 'fammix.com', 'fansworldwide.de',
    'fantasymail.de', 'fastacura.com', 'fastchevy.com',
    'fastchrysler.com', 'fastkawasaki.com', 'fastmazda.com',
    'fastmitsubishi.com', 'fastnissan.com', 'fastsubaru.com',
    'fastsuzuki.com', 'fasttoyota.com', 'fastyamaha.com',
    'fatflap.com', 'fdfdsfds.com', 'fightallspam.com',
    'fiifke.de', 'filzmail.com', 'fivemail.de',
    'fixmail.tk', 'fizmail.com', 'flyspam.com',
    'footard.com', 'forgetmail.com', 'fr33mail.info',
    'frapmail.com', 'friendlymail.co.uk', 'front14.org',
    'fuckingduh.com', 'fudgerub.com', 'fux0ringduh.com',
    'garliclife.com', 'gehensiull.com', 'get1mail.com',
    'get2mail.fr', 'getonemail.com', 'getonemail.net',
    'ghosttexter.de', 'gishpuppy.com', 'goemailgo.com',
    'gorillaswithdirtyarmpits.com', 'gotmail.com', 'gotmail.net',
    'gotmail.org', 'gotti.otherinbox.com', 'gowikibooks.com',
    'gowikicampus.com', 'gowikicars.com', 'gowikifilms.com',
    'gowikigames.com', 'gowikimusic.com', 'gowikinetwork.com',
    'gowikitravel.com', 'gowikitv.com', 'grandmamail.com',
    'grandmasmail.com', 'great-host.in', 'greensloth.com',
    'gsrv.co.uk', 'guerillamail.biz', 'guerillamail.com',
    'guerillamail.de', 'guerillamail.info', 'guerillamail.net',
    'guerillamail.org', 'guerrillamail.info', 'h.mintemail.com',
    'h8s.org', 'hacccc.com', 'haltospam.com',
    'harakirimail.com', 'hartbot.de', 'hatespam.org',
    'herp.in', 'hidemail.de', 'hidzz.com',
    'hmamail.com', 'hochsitze.com', 'hopemail.biz',
    'hotpop.com', 'hulapla.de', 'humn.ws.ทดสอบ.com',
    'ieatspam.eu', 'ieatspam.info', 'ieh-mail.de',
    'ihateyoualot.info', 'iheartspam.org', 'imails.info',
    'imgof.com', 'imgv.de', 'imstations.com',
    'inbax.tk', 'inbox.si', 'inboxalias.com',
    'inboxclean.com', 'inboxclean.org', 'incognitomail.com',
    'incognitomail.net', 'incognitomail.org', 'infocom.zp.ua',
    'insorg-mail.info', 'instant-mail.de', 'instantemailaddress.com',
    'iozak.com', 'ip6.li', 'ipoo.org',
    'irish2me.com', 'iwi.net', 'jetable.com',
    'jetable.fr.nf', 'jetable.net', 'jetable.org',
    'jnxjn.com', 'jourrapide.com', 'jsrsolutions.com',
    'junk1.com', 'kasmail.com', 'kaspop.com',
    'keepmymail.com', 'killmail.com', 'killmail.net',
    'kimsdisk.com', 'kingsq.ga', 'kiois.com',
    'kloap.com', 'klzlv.com', 'kook.ml',
    'kulturbetrieb.info', 'kurzepost.de', 'l33r.eu',
    'labetteravede.at', 'lackmail.net', 'lags.us',
    'landmail.co', 'lastmail.co', 'lawlita.com',
    'lazyinbox.com', 'legitmail.club', 'letthemeatspam.com',
    'lhsdv.com', 'lifebyfood.com', 'link2mail.net',
    'litedrop.com', 'loadby.us', 'login-email.cf',
    'login-email.ga', 'login-email.ml', 'login-email.tk',
    'lol.ovpn.to', 'lookugly.com', 'lopl.co.cc',
    'lortemail.dk', 'lovemeleaveme.com', 'lr78.com',
    'lroid.com', 'lukop.dk', 'm4ilweb.info',
    'maboard.com', 'mail-hierarchie.net', 'mail-temporaire.fr',
    'mail.by', 'mail.mezimages.net', 'mail.zp.ua',
    'mail114.net', 'mail2rss.org', 'mail333.com',
    'mail4trash.com', 'mailbidon.com', 'mailblocks.com',
    'mailcatch.com', 'maildrop.cc', 'maildrop.cf',
    'maildrop.ga', 'maildrop.gq', 'maildrop.ml',
    'maildu.de', 'maildx.com', 'mailed.ro',
    'mailexpire.com', 'mailfa.tk', 'mailforspam.com',
    'mailfree.ga', 'mailfree.gq', 'mailfree.ml',
    'mailfreeonline.com', 'mailfs.com', 'mailguard.me',
    'mailhazard.com', 'mailhazard.us', 'mailhz.me',
    'mailimate.com', 'mailin8r.com', 'mailinater.com',
    'mailinator.co.uk', 'mailinator.gq', 'mailinator.info',
    'mailinator.us', 'mailincubator.com', 'mailismagic.com',
    'mailjunk.cf', 'mailjunk.ga', 'mailjunk.gq',
    'mailjunk.ml', 'mailjunk.tk', 'mailmate.com',
    'mailme.gq', 'mailme.ir', 'mailme.lv',
    'mailme24.com', 'mailmetrash.com', 'mailmoat.com',
    'mailnator.com', 'mailnesia.com', 'mailnull.com',
    'mailorg.org', 'mailpick.biz', 'mailrock.biz',
    'mailsac.com', 'mailseal.de', 'mailshell.com',
    'mailsiphon.com', 'mailslapping.com', 'mailslite.com',
    'mailspam.xyz', 'mailtemp.info', 'mailtothis.com',
    'mailzilla.com', 'mailzilla.org', 'makemetheking.com',
    'malahov.de', 'manifestgenerator.com', 'manybrain.com',
    'mbx.cc', 'mega.zik.dj', 'meinspamschutz.de',
    'meltmail.com', 'messagebeamer.de', 'mezimages.net',
    'mierdamail.com', 'migmail.pl', 'migumail.com',
    'mintemail.com', 'mjukgansen.nu', 'moakt.com',
    'mobi.web.id', 'mobileninja.co.uk', 'moburl.com',
    'mockmyid.com', 'mohmal.com', 'moncourrier.fr.nf',
    'monemail.fr.nf', 'monmail.fr.nf', 'monumentmail.com',
    'ms51.hinet.net', 'msb.minsmail.com', 'msgos.com',
    'mspeciosa.com', 'mswork.ru', 'mt2009.com',
    'mt2014.com', 'myalias.pw', 'mycleaninbox.net',
    'myemailboxy.com', 'mymail-in.net', 'mymailoasis.com',
    'mynetstore.de', 'mypacks.net', 'mypartyclip.de',
    'myphantomemail.com', 'myspaceinc.com', 'myspaceinc.net',
    'myspacepimpedup.com', 'myspamless.com', 'mytempemail.com',
    'mytempmail.com', 'mytrashmail.com', 'nabuma.com',
    'neomailbox.com', 'nepwk.com', 'nervmich.net',
    'nervtmansen.net', 'netmails.com', 'netmails.net',
    'netzidiot.de', 'neverbox.com', 'nice-4u.com',
    'nincsmail.hu', 'nmail.cf', 'nobulk.com',
    'noclickemail.com', 'nogmailspam.info', 'nomail.pw',
    'nomail.xl.cx', 'nomail2me.com', 'nomorespamemails.com',
    'nonspam.eu', 'nonspammer.de', 'noproxy.ru',
    'nosam.org', 'nospam.ze.tc', 'nospam4.us',
    'nospamfor.us', 'nospammail.net', 'nospamthanks.info',
    'notmailinator.com', 'nowhere.org', 'nowmymail.com',
    'ntlhelp.net', 'nullbox.info', 'nurfuerspam.de',
    'nus.edu.sg', 'nwldx.com', 'objectmail.com',
    'obobbo.com', 'odnorazovoe.ru', 'ohaaa.de',
    'omail.pro', 'oneoffemail.com', 'onewaymail.com',
    'onlatedotcom.info', 'online.ms', 'oopi.org',
    'opayq.com', 'ordinaryamerican.net', 'otherinbox.com',
    'ourklips.com', 'outlawspam.com', 'ovpn.to',
    'owlpic.com', 'pancakemail.com', 'pimpedupmyspace.com',
    'pjjkp.com', 'plexolan.de', 'poczta.onet.pl',
    'politikerclub.de', 'poofy.org', 'pookmail.com',
    'pop3.xyz', 'privacy.net', 'privy-mail.com',
    'privymail.de', 'proxymail.eu', 'prtnx.com',
    'punkass.com', 'putthisinyourspamdatabase.com',
    'pwrby.com', 'q314.net', 'qisdo.com',
    'qisoa.com', 'qoika.com', 'quickinbox.com',
    'quickmail.nl', 'rainmail.biz', 'rcpt.at',
    'reallymymail.com', 'realtyalerts.ca', 'recode.me',
    'recursor.net', 'recyclemail.dk', 'regbypass.com',
    'regbypass.comsafe-mail.net', 'rejectmail.com', 'remail.cf',
    'rhyta.com', 'rklips.com', 'rmqkr.net',
    'royal.net', 'rppkn.com', 'rtotlmail.net',
    'rtrtr.com', 's0ny.net', 'safe-mail.net',
    'safersignup.de', 'safetymail.info', 'safetypost.de',
    'sandelf.de', 'saynotospams.com', 'schafmail.de',
    'schrott-email.de', 'secretemail.de', 'secure-mail.biz',
    'selfdestructingmail.com', 'senseless-entertainment.com',
    'server.ms.selfip.net', 'sharklasers.com', 'shieldemail.com',
    'shiftmail.com', 'shitaway.cf', 'shitaway.cu.cc',
    'shitaway.ga', 'shitaway.gq', 'shitaway.ml',
    'shitaway.tk', 'shitmail.de', 'shitmail.me',
    'shitmail.org', 'shortmail.net', 'showslow.de',
    'sibmail.com', 'sinnlos-mail.de', 'siteposter.net',
    'skeefmail.com', 'slaskpost.se', 'slave-auctions.net',
    'slopsbox.com', 'slushmail.com', 'smapfree24.com',
    'smapfree24.de', 'smapfree24.eu', 'smapfree24.info',
    'smapfree24.org', 'smashmail.de', 'smellfear.com',
    'smellrear.com', 'snakemail.com', 'sneakemail.com',
    'sneakmail.de', 'snkmail.com', 'sofimail.com',
    'sofort-mail.de', 'sofortmail.de', 'sogetthis.com',
    'sohu.com', 'soisz.com', 'solvemail.info',
    'soodo.com', 'soodonims.com', 'spam.la',
    'spam.su', 'spam4.me', 'spamail.de',
    'spamarrest.com', 'spamavert.com', 'spambob.com',
    'spambob.net', 'spambob.org', 'spambog.com',
    'spambog.de', 'spambog.net', 'spambog.ru',
    'spambox.info', 'spambox.irishspringrealty.com', 'spambox.us',
    'spamcannon.com', 'spamcannon.net', 'spamcero.com',
    'spamcon.org', 'spamcorptastic.com', 'spamcowboy.com',
    'spamcowboy.net', 'spamcowboy.org', 'spamday.com',
    'spameater.com', 'spameater.org', 'spamex.com',
    'spamfighter.cf', 'spamfighter.ga', 'spamfighter.gq',
    'spamfighter.ml', 'spamfighter.tk', 'spamfree.eu',
    'spamfree24.com', 'spamfree24.de', 'spamfree24.eu',
    'spamfree24.info', 'spamfree24.net', 'spamfree24.org',
    'spamgoes.in', 'spamgourmet.com', 'spamgourmet.net',
    'spamgourmet.org', 'spamherelots.com', 'spamhereplease.com',
    'spamhole.com', 'spamify.com', 'spaminator.de',
    'spamkill.info', 'spaml.com', 'spaml.de',
    'spammotel.com', 'spamobox.com', 'spamoff.de',
    'spamsalad.in', 'spamslicer.com', 'spamspot.com',
    'spamthis.co.uk', 'spamthisplease.com', 'spamtrail.com',
    'spamtroll.net', 'speed.1s.fr', 'spoofmail.de',
    'squizzy.de', 'ssoia.com', 'startkeys.com',
    'stexsy.com', 'stop-my-spam.cf', 'stop-my-spam.com',
    'stop-my-spam.ga', 'stop-my-spam.ml', 'stop-my-spam.tk',
    'streetwisemail.com', 'stuffmail.de', 'supergreatmail.com',
    'supermailer.jp', 'superrito.com', 'superstachel.de',
    'suremail.info', 'svk.jp', 'sweetxxx.de',
    'tafmail.com', 'tagyourself.com', 'talkinator.com',
    'tapchicuoihoi.com', 'techemail.com', 'techgroup.me',
    'teleworm.com', 'teleworm.us', 'temp-mail.de',
    'temp-mail.org', 'temp-mail.ru', 'temp.emeraldwebmail.com',
    'temp.headstrong.de', 'tempalias.com', 'tempe-mail.com',
    'tempemail.biz', 'tempemail.co.za', 'tempemail.com',
    'tempemail.net', 'tempinbox.co.uk', 'tempinbox.com',
    'tempmail.co', 'tempmail.de', 'tempmail.eu',
    'tempmail.it', 'tempmail.net', 'tempmail.us',
    'tempmail2.com', 'tempmaildemo.com', 'tempmailer.com',
    'tempmailer.de', 'tempomail.fr', 'temporarily.de',
    'temporarioemail.com.br', 'temporaryemail.net', 'temporaryemail.us',
    'temporaryforwarding.com', 'temporaryinbox.com', 'tempthe.net',
    'thankyou2010.com', 'thecloudindex.com', 'thelimestones.com',
    'thisisnotmyrealemail.com', 'throam.com', 'throwam.com',
    'throwawayemailaddress.com', 'throwawaymail.com', 'tilien.com',
    'tittbit.in', 'tizi.com', 'tmailinator.com',
    'toiea.com', 'toomail.biz', 'topranklist.de',
    'tradermail.info', 'trash-amil.com', 'trash-mail.at',
    'trash-mail.com', 'trash-mail.de', 'trash-mail.ga',
    'trash-mail.gq', 'trash-mail.ml', 'trash-mail.tk',
    'trash2009.com', 'trash2010.com', 'trash2011.com',
    'trashbox.eu', 'trashcanmail.com', 'trashdevil.com',
    'trashdevil.de', 'trashemail.de', 'trashmail.at',
    'trashmail.com', 'trashmail.de', 'trashmail.me',
    'trashmail.net', 'trashmail.org', 'trashmail.ws',
    'trashmailer.com', 'trashymail.com', 'trashymail.net',
    'trbvm.com', 'trbvn.com', 'trialmail.de',
    'trickmail.net', 'trillianpro.com', 'trimix.cn',
    'trollbox.us', 'trungtamtoeic.com', 'tryalert.com',
    'ttszuo.xyz', 'tualias.com', 'turoid.com',
    'turual.com', 'tvchd.com', 'twinmail.de',
    'tyldd.com', 'ubismail.net', 'uggsrock.com',
    'umail.net', 'upliftnow.com', 'uplipht.com',
    'uroid.com', 'us.af', 'username.e4ward.com',
    'valemail.net', 'venompen.com', 'veryrealemail.com',
    'viditag.com', 'viewcastmedia.com', 'viewcastmedia.net',
    'viewcastmedia.org', 'viralplays.com', 'vkcode.ru',
    'vmani.com', 'vomoto.com', 'vpn.st',
    'vsimcard.com', 'vubby.com', 'wasteland.rfc822.org',
    'webemail.me', 'webm4il.info', 'webuser.in',
    'wee.my', 'weg-werf-email.de', 'wegwerf-emails.de',
    'wegwerfadresse.de', 'wegwerfemail.com', 'wegwerfemail.de',
    'wegwerfmail.de', 'wegwerfmail.info', 'wegwerfmail.net',
    'wegwerfmail.org', 'wetrainbayarea.com', 'wetrainbayarea.org',
    'wh4f.org', 'whatiaas.com', 'whatpaas.com',
    'whopy.com', 'whtjddn.33mail.com', 'whyspam.me',
    'wilemail.com', 'willhackforfood.biz', 'willselfdestruct.com',
    'winemaven.info', 'wolfsmail.tk', 'wollan.info',
    'worldspace.link', 'wronghead.com', 'wuzup.net',
    'wuzupmail.net', 'wwwnew.eu', 'x.ip6.li',
    'xagloo.co', 'xagloo.com', 'xemaps.com',
    'xents.com', 'xmaily.com', 'xoxy.net',
    'yapped.net', 'yeah.net', 'yep.it',
    'yogamaven.com', 'yopmail.com', 'yopmail.fr',
    'yopmail.gq', 'yopmail.net', 'you-spam.com',
    'yourdomain.com', 'ypmail.webarnak.fr.eu.org', 'yuurok.com',
    'z1p.biz', 'za.com', 'zehnminuten.de',
    'zehnminutenmail.de', 'zippymail.info', 'zoaxe.com',
    'zoemail.com', 'zoemail.net', 'zoemail.org',
    'zomg.info', 'zxcv.com', 'zxcvbnm.com',
    'zzz.com',
}

# Suspicious TLDs often used for disposable emails
SUSPICIOUS_TLDS = {
    '.tk', '.ml', '.ga', '.gq', '.cf',  # Free domains
    '.xyz', '.top', '.work', '.click', '.link',  # Cheap domains
    '.bid', '.loan', '.racing', '.download', '.stream',
}

# Email patterns that suggest abuse
SUSPICIOUS_PATTERNS = [
    r'^test\d*@',  # test123@
    r'^temp\d*@',  # temp123@
    r'^fake\d*@',  # fake123@
    r'^\d{5,}@',   # 12345678@
    r'^[a-z]{1,3}\d{3,}@',  # abc123456@
    r'^noreply@',
    r'^donotreply@',
    r'^spam@',
    r'^throwaway',
    r'disposable',
    r'tempmail',
    r'mailinator',
    r'guerrilla',
]


def is_disposable_email(email):
    """
    Check if an email address is from a disposable email provider.
    
    Args:
        email: The email address to check
        
    Returns:
        tuple: (is_disposable: bool, reason: str or None)
    """
    if not email:
        return True, "Email is required"
    
    email = email.lower().strip()
    
    # Validate basic email format
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return True, "Invalid email format"
    
    try:
        local_part, domain = email.rsplit('@', 1)
    except ValueError:
        return True, "Invalid email format"
    
    # Check if domain is in disposable list
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return True, f"Disposable email domains like {domain} are not allowed. Please use your real email."
    
    # Check for subdomains of disposable domains
    for disposable in DISPOSABLE_EMAIL_DOMAINS:
        if domain.endswith('.' + disposable):
            return True, f"This email domain is not allowed. Please use your real email."
    
    # Check suspicious TLDs
    for tld in SUSPICIOUS_TLDS:
        if domain.endswith(tld):
            # Don't block outright, but flag for additional verification
            logger.warning(f"Email with suspicious TLD: {email}")
    
    # Check suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, email, re.IGNORECASE):
            return True, "This email address looks temporary. Please use your real email."
    
    # Check for plus addressing abuse (many + signs)
    if local_part.count('+') > 2:
        return True, "This email format is not allowed."
    
    return False, None


def is_suspicious_email(email):
    """
    Check if an email might be suspicious (but not definitely disposable).
    Returns a risk score from 0-100.
    """
    if not email:
        return 100
    
    email = email.lower().strip()
    score = 0
    
    try:
        local_part, domain = email.rsplit('@', 1)
    except ValueError:
        return 100
    
    # Check for suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, email, re.IGNORECASE):
            score += 30
    
    # Check suspicious TLDs
    for tld in SUSPICIOUS_TLDS:
        if domain.endswith(tld):
            score += 20
    
    # Check for numeric-heavy local part
    digits = sum(c.isdigit() for c in local_part)
    if digits > len(local_part) * 0.5:
        score += 15
    
    # Check for very short local part
    if len(local_part) <= 3:
        score += 10
    
    # Check for plus addressing
    if '+' in local_part:
        score += 5
    
    # Check for dots abuse
    if local_part.count('.') > 3:
        score += 10
    
    return min(score, 100)


def get_email_domain_info(email):
    """
    Get information about the email domain for risk assessment.
    """
    if not email:
        return None
    
    try:
        local_part, domain = email.lower().rsplit('@', 1)
    except ValueError:
        return None
    
    is_disposable, reason = is_disposable_email(email)
    risk_score = is_suspicious_email(email)
    
    return {
        'email': email,
        'domain': domain,
        'local_part': local_part,
        'is_disposable': is_disposable,
        'block_reason': reason,
        'risk_score': risk_score,
        'has_plus_addressing': '+' in local_part,
        'is_high_risk': risk_score >= 50,
    }


def validate_email_for_signup(email):
    """
    Validate email for account signup.
    Blocks disposable emails and returns appropriate error message.
    
    Args:
        email: The email address to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    is_disposable, reason = is_disposable_email(email)
    
    if is_disposable:
        logger.warning(f"Blocked signup attempt with disposable email: {email}")
        return False, reason
    
    # Check risk score
    risk_score = is_suspicious_email(email)
    if risk_score >= 70:
        logger.warning(f"High risk email signup attempt: {email} (score: {risk_score})")
        # Don't block but flag for manual review
    
    return True, None


def add_to_blocklist(domain):
    """
    Add a domain to the blocklist dynamically.
    This updates the in-memory set (for immediate effect) 
    but should also be persisted to a database for durability.
    """
    global DISPOSABLE_EMAIL_DOMAINS
    domain = domain.lower().strip()
    DISPOSABLE_EMAIL_DOMAINS.add(domain)
    logger.info(f"Added {domain} to disposable email blocklist")


def get_blocklist_stats():
    """Get statistics about the email blocklist."""
    return {
        'total_domains_blocked': len(DISPOSABLE_EMAIL_DOMAINS),
        'suspicious_tlds': len(SUSPICIOUS_TLDS),
        'suspicious_patterns': len(SUSPICIOUS_PATTERNS),
    }
