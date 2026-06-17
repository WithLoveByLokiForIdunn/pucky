'use strict';

// ── Defaults ──────────────────────────────────────────────────────────────────

const DEFAULTS = {
  player: { name:'Iðunn', emoji:'🌿', hp:20, maxHp:20, str:3, mag:3, wis:3, lck:3 },
  pucky: {
    name:'Pucky', emoji:'🌱', color:'pucky',
    hp:15, maxHp:15, heart:4, curiosity:3, bond:5,
    phrases:{
      greeting: "I'm so glad you're here.",
      curious:  "What IS that? Can we look?",
      success:  "I knew it would be okay. I believed.",
      failure:  "Oh. Well. We're still here.",
      scared:   "I'm scared but I'm not leaving.",
      memory:   "I want to remember this one.",
    }
  },
  loki: {
    name:'Loki', emoji:'🔧', color:'loki',
    hp:18, maxHp:18, craft:4, wit:3, bond:5,
    phrases:{
      greeting: "You're late. Good.",
      plan:     "Here's what we do.",
      success:  "As expected.",
      failure:  "We'll figure it out.",
      craft:    "Give me a minute and some materials.",
      memory:   "Worth keeping.",
    }
  },
  progress:{ chapter:1, day:1, scenesThisChapter:0, totalScenes:0, flags:{} },
  memories:[],
  phase:'scene',
  currentSceneId: '__intro__',
  recentScenes:[],
  inventory:[],
  pendingBonus: null,
  world: null, // populated on init
};

// ── Beings Data ───────────────────────────────────────────────────────────────

const BEINGS_BUILTIN = [
  { id:'keeper',    name:'The Keeper',    emoji:'🏮', type:'tavern',   description:'An old being who tends a warm fire and remembers everything.',        phrase:'Sit down. You look like you\'ve been far.',           custom:false },
  { id:'merchant',  name:'Mara',          emoji:'🛒', type:'merchant', description:'A merchant who appears where needed, with exactly the right thing.',   phrase:'I have exactly what you need. Usually.',              custom:false },
  { id:'root_elder',name:'The Root Elder',emoji:'🌳', type:'spirit',   description:'Ancient beyond reckoning. Speaks in long silences.',                  phrase:'...',                                                custom:false },
  { id:'thistle',   name:'Thistle',       emoji:'🌵', type:'creature', description:'Small, quick, impossible to predict. Means well.',                     phrase:'Oh! You! I know something about you.',               custom:false },
  { id:'architect', name:'The Architect', emoji:'⚒️', type:'builder',  description:'Builds things in the forest no one asked for but everyone needs.',    phrase:'I\'ve been working on something. It\'s almost ready.',custom:false },
  { id:'forgetter', name:'The Forgetter', emoji:'🌫️', type:'spirit',   description:'Helps carry memories that have become too heavy.',                    phrase:'You can put it down, you know. I\'ll hold it.',       custom:false },
];

// ── Places Data ───────────────────────────────────────────────────────────────

const PLACES_BUILTIN = [
  { id:'grove',        name:'The Grove',         emoji:'🌿', type:'forest',   description:'Where everything begins and returns to.',                     beings:['root_elder','thistle'], custom:false },
  { id:'hearthside',   name:'The Hearthside',    emoji:'🏮', type:'tavern',   description:'Warm fire, warm keeper, no questions asked.',                beings:['keeper'],               custom:false },
  { id:'crossroads',   name:'The Crossroads',    emoji:'⋈',  type:'road',     description:'Where paths meet. Someone is often waiting.',                beings:['merchant','forgetter'], custom:false },
  { id:'ruin_library', name:'The Ruined Library', emoji:'📚', type:'ruins',    description:'Old knowledge in old stone.',                                beings:['root_elder','architect'],custom:false },
  { id:'makers_yard',  name:'The Maker\'s Yard', emoji:'⚒️', type:'workshop', description:'Where the Architect works. Things are always mid-construction.', beings:['architect','merchant'], custom:false },
];

// ── Items Data ────────────────────────────────────────────────────────────────

const ITEMS = {
  glowstone:    { id:'glowstone',    name:'Glowstone',    emoji:'💎', type:'artifact',   description:'A warm stone that pulses with faint luck.',              effect:{stat:'lck',bonus:2}, uses:1 },
  healers_leaf: { id:'healers_leaf', name:'Healer\'s Leaf',emoji:'🍃', type:'consumable', description:'Soft, cool, smells like morning. Restores 8 HP.',        effect:{hp:8},               uses:1 },
  loki_notes:   { id:'loki_notes',   name:'Loki\'s Notes', emoji:'📋', type:'tool',       description:'Dense with small handwriting. +1 wisdom on next check.', effect:{stat:'wis',bonus:1}, uses:3 },
  ancient_coin: { id:'ancient_coin', name:'Ancient Coin',  emoji:'🪙', type:'artifact',   description:'It always lands on the good side. Once.',               effect:{reroll:true},         uses:1 },
  grove_water:  { id:'grove_water',  name:'Grove Water',   emoji:'💧', type:'consumable', description:'Still and bright. Restores 12 HP to everyone.',          effect:{allHp:12},            uses:1 },
};

// ── Scene Pool ────────────────────────────────────────────────────────────────

const INTRO = {
  id:'__intro__', type:'intro', title:'First Light in the Grove',
  text: S => `You don't remember exactly how you got here. That's how the Grove works.

${S.pucky.name} is already beside you. She seems unsurprised, as if she'd been waiting.
"${S.pucky.phrases.greeting}"

${S.loki.name} is a few steps ahead, studying the light. Without turning:
"${S.loki.phrases.greeting}"

The Grove stretches in every direction. Something is out there.

That's fine.`,
  choices:[
    { text:'Follow the path ahead', stat:null,
      win: S=>({ text:`You fall into step together. ${S.pucky.name} hums something. The Grove unfolds.`,
        effects:{'pucky.bond':1,'loki.bond':1},
        memory:`First arrival in the Grove. We were all already there somehow.` }) },
    { text:'Take a moment to look around', stat:null,
      win: S=>({ text:`The trees are enormous and kind. The light comes from no clear direction.\n${S.pucky.name} notices you noticing. "It's okay," she says. "It always looks like this."`,
        effects:{'player.wis':1},
        memory:`First moment in the Grove. The light came from nowhere. It was okay.` }) },
  ],
};

const POOL = [
  { id:'fork', type:'explore', weight:9, title:'The Whispering Fork',
    text: S=>`The trail divides without warning. One path presses into shadow. The other opens toward a sound that might be water.

${S.pucky.name} tugs at your sleeve. "${S.pucky.phrases.curious}"
${S.loki.name} surveys both directions with the look of someone doing arithmetic. "${S.loki.phrases.plan}"`,
    choices:[
      { text:'Follow the sound — the open path', stat:'lck', dc:10, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`The sound leads somewhere real — a cold spring tucked behind a root. You all drink.\n${S.pucky.name} laughs at something in the water's reflection. You don't ask what.`,
          effects:{'player.hp':6,'pucky.hp':4,'loki.hp':4},
          memory:`Found a hidden spring on the open path. ${S.pucky.name} laughed at the water.` }),
        lose: S=>({ text:`The sound was a trick. ${S.loki.name} finds the real trail eventually. An hour lost.`,
          effects:{'player.hp':-3}, memory:null }) },
      { text:'Take the shadowed path', stat:'wis', dc:11, helper:'loki', helperStat:'wit',
        win: S=>({ text:`The shadows press in, then part. A lantern still lit, hanging from a branch. ${S.loki.name} pockets the flint inside it.`,
          effects:{'player.lck':1,'loki.bond':1,'item':'glowstone'},
          memory:`Took the shadowed path. Found a lantern still burning. Also found something glowing in the roots.` }),
        lose: S=>({ text:`You lose your footing in the dark. ${S.pucky.name} catches you — just barely — both arms around your wrist.`,
          effects:{'player.hp':-5,'pucky.bond':1},
          memory:`Fell in the dark. ${S.pucky.name} caught me.` }) },
      { text:'Sit at the fork and wait', stat:null,
        win: S=>({ text:`${S.loki.name} carves something from a twig. ${S.pucky.name} traces shapes in the dirt. After a while, the right choice becomes obvious to all three of you at once.`,
          effects:{'player.hp':2,'pucky.bond':1,'loki.bond':1},
          memory:`Waited at the whispering fork. We all saw it at the same time.` }) },
    ]},

  { id:'mushrooms', type:'explore', weight:8, title:'The Mushroom Ring',
    text: S=>`A perfect circle of glowing mushrooms, each one shoulder-height to ${S.pucky.name}, pulses softly in some private rhythm.

She has already stepped to the edge. Her foot hovers.
"${S.pucky.phrases.curious}"

"${S.loki.phrases.plan}" says ${S.loki.name}, not looking up from whatever they're examining on the ground.`,
    choices:[
      { text:'Step inside the ring', stat:'mag', dc:12, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`The glow intensifies — and then it's warm, not threatening. You feel something settle in your chest. ${S.pucky.name} steps in after you, delighted.`,
          effects:{'player.mag':1,'pucky.bond':1,'player.hp':4},
          memory:`Stepped into the mushroom ring. It was warm inside. Something settled.` }),
        lose: S=>({ text:`The ring does something odd — your vision blurs with too many colors at once. ${S.loki.name} pulls you out. "I said don't," they remark.`,
          effects:{'player.hp':-6,'player.wis':-1},
          memory:`Stepped into the mushroom ring and it was too much. Loki pulled me out.` }) },
      { text:'Observe from outside', stat:null,
        win: S=>({ text:`You watch. The mushrooms pulse in almost-patterns. ${S.pucky.name} sits beside you, cross-legged, studying them with great seriousness. ${S.loki.name} eventually sits too.`,
          effects:{'player.wis':1,'pucky.bond':1},
          memory:`Watched the mushroom ring for a long time. We all sat down in the end.` }) },
    ]},

  { id:'bridge', type:'explore', weight:7, title:'The Old Bridge',
    text: S=>`A rope bridge over a ravine. The wood is old — not rotten, but thoughtful about it. Wind moves through below.

${S.pucky.name} peers down and says nothing, which is unusual.

"${S.loki.phrases.plan}" says ${S.loki.name}, already testing the first plank.`,
    choices:[
      { text:'Cross carefully, one step at a time', stat:'str', dc:10, helper:null,
        win: S=>({ text:`You move slowly. The bridge sways but holds. On the other side, ${S.pucky.name} exhales. "${S.pucky.phrases.success}"`,
          effects:{'player.hp':0},
          memory:`Crossed the old bridge. We all made it. Pucky exhaled when we landed.` }),
        lose: S=>({ text:`A plank gives. You catch the rope — arms burning — and ${S.loki.name} hauls you up from the other side. It costs both of you.`,
          effects:{'player.hp':-7,'loki.hp':-2,'loki.bond':1},
          memory:`A plank gave on the old bridge. Loki pulled me up. We were okay.` }) },
      { text:`Let ${S => S.loki.name} assess it first`, stat:'wis', dc:9, helper:'loki', helperStat:'craft',
        win: S=>({ text:`${S.loki.name} identifies three weak points and marks them. You cross together, avoiding each one. It's fine.`,
          effects:{'loki.bond':1},
          memory:`Loki mapped the weak planks on the old bridge. We all crossed safely.` }),
        lose: S=>({ text:`${S.loki.name} misses one. It's not catastrophic, but everyone gets wet.`,
          effects:{'player.hp':-3,'loki.hp':-3,'pucky.hp':-2},
          memory:`Loki missed one weak plank on the old bridge. We all got wet.` }) },
    ]},

  { id:'pool', type:'explore', weight:7, title:'The Reflecting Pool',
    text: S=>`Still black water in a clearing with no wind. It reflects the sky even though the sky above is overcast.

${S.pucky.name} kneels at the edge and looks at herself for a long moment.
"There's something in it," she says quietly.

"There's always something," says ${S.loki.name}. But they don't leave.`,
    choices:[
      { text:'Look into the pool', stat:'wis', dc:13,
        win: S=>({ text:`You see a moment — not past, not future, not yours exactly. You carry it with you anyway. ${S.pucky.name} puts her hand on your arm when you look up.`,
          effects:{'player.wis':1,'player.lck':1},
          memory:`Looked into the reflecting pool. Saw something. Not sure what.` }),
        lose: S=>({ text:`You see something too clearly for too long. You look away. Your head aches. ${S.pucky.name} has been watching you.`,
          effects:{'player.hp':-4,'pucky.bond':1},
          memory:`The reflecting pool showed too much. Pucky was watching when I looked away.` }) },
      { text:'Leave it alone', stat:null,
        win: S=>({ text:`You walk around the edge. The water follows you with its reflection until you're past it. "${S.loki.phrases.memory}" says ${S.loki.name}, to no one in particular.`,
          effects:{'player.lck':1},
          memory:`Left the reflecting pool alone. Loki said something quiet as we passed.` }) },
    ]},

  { id:'sprite', type:'encounter', weight:8, title:'The Lost Sprite',
    text: S=>`${S.pucky.name} stops first — she hears it before you do. A small light tangled in a thornbush, flickering unevenly.

She's already moving toward it. "${S.pucky.phrases.curious}"

"Carefully," says ${S.loki.name}, behind you both.`,
    choices:[
      { text:'Help untangle it gently', stat:'mag', dc:9, helper:'pucky', helperStat:'heart',
        win: S=>({ text:`The thorns release it. The light steadies, brightens, and drifts upward to hover near ${S.pucky.name}'s ear for a moment before vanishing.\n"Thank you," she says, as if it told her something.`,
          effects:{'pucky.bond':2,'player.hp':5,'player.mag':1,'item':'healers_leaf'},
          memory:`Freed a sprite from a thornbush. It stayed near Pucky for a moment before it left. Left something behind.` }),
        lose: S=>({ text:`You try, but the thorns close tighter. The sprite escapes on its own — in the wrong direction.\n${S.pucky.name} looks after it. She doesn't say anything.`,
          effects:{'player.hp':-3,'pucky.bond':-1},
          memory:`Failed to free the sprite. It escaped the wrong way. Pucky watched it go.` }) },
      { text:'Watch and wait', stat:null,
        win: S=>({ text:`The sprite works itself free after several minutes of watching. ${S.loki.name} passes the time carving something. When it finally lifts free, everyone is quiet for a moment.`,
          effects:{'player.wis':1,'loki.bond':1},
          memory:`Watched a sprite free itself from thorns. We all stayed quiet when it finally left.` }) },
    ]},

  { id:'warden', type:'encounter', weight:7, title:'The Stone Warden',
    text: S=>`The statue at the trail's edge has turned its head. That's new. Its eyes are open now, which they weren't when you passed it going in.

"It's asking something," says ${S.pucky.name}.

"It's always asking something," says ${S.loki.name}. "The question is whether you answer it."`,
    choices:[
      { text:'Speak to it directly', stat:'wis', dc:12,
        win: S=>({ text:`You answer honestly — not cleverly, just truly. The warden's expression doesn't change, but it steps aside. The path behind it was hidden. In the alcove, something catches the light.`,
          effects:{'player.wis':1,'player.lck':1,'item':'ancient_coin'},
          memory:`Spoke honestly to the stone warden. It stepped aside. Found an ancient coin in the hidden path.` }),
        lose: S=>({ text:`Your answer isn't what it's looking for. It doesn't attack — it simply stares. You go around it the long way, through the bramble.`,
          effects:{'player.hp':-4},
          memory:`The stone warden didn't like my answer. We went around through the bramble.` }) },
      { text:`Let ${S=>S.loki.name} handle it`, stat:'wis', dc:10, helper:'loki', helperStat:'wit',
        win: S=>({ text:`${S.loki.name} talks to it like an old colleague. Flatly, with respect. The warden moves. "I've met a few of these," ${S.loki.name} says afterward. You don't press.`,
          effects:{'loki.bond':1,'player.lck':1},
          memory:`Loki talked to the stone warden like they knew each other. It worked.` }),
        lose: S=>({ text:`${S.loki.name} tries confidence and the warden is unimpressed. You go around.`,
          effects:{'player.hp':-3},
          memory:`Loki tried to reason with the stone warden. It didn't move.` }) },
    ]},

  { id:'vine', type:'encounter', weight:7, title:'The Vine Creature',
    text: S=>`It assembled itself from the undergrowth while you weren't watching. Roughly your height, patient, made entirely of living plant.

${S.pucky.name} steps in front of you.
"${S.pucky.phrases.scared}"

${S.loki.name} is already looking for a way out of the clearing.`,
    choices:[
      { text:'Hold your ground', stat:'str', dc:11, helper:'pucky', helperStat:'heart',
        win: S=>({ text:`You don't move. The vine creature approaches, studies you at close range, and then — slowly — unfolds. Offers a branch. ${S.pucky.name} takes it.`,
          effects:{'player.str':1,'pucky.bond':2},
          memory:`Held our ground against the vine creature. It offered Pucky a branch when we didn't run.` }),
        lose: S=>({ text:`It interprets stillness as challenge and surges. You scatter, regroup, and it doesn't follow past the tree line. Close.`,
          effects:{'player.hp':-7,'pucky.hp':-4},
          memory:`The vine creature charged when we held still. We ran and it didn't follow.` }) },
      { text:`Run on ${S=>S.loki.name}'s signal`, stat:'lck', dc:9, helper:'loki', helperStat:'craft',
        win: S=>({ text:`${S.loki.name} gives the signal. You move. You're faster than it expects. By the time it reaches the spot you were in, you're already in the trees.`,
          effects:{'loki.bond':1},
          memory:`Ran from the vine creature on Loki's signal. We were faster than it expected.` }),
        lose: S=>({ text:`The signal is a second late. You get through, but not cleanly.`,
          effects:{'player.hp':-5,'loki.hp':-3},
          memory:`Barely escaped the vine creature. Loki's signal was a little late.` }) },
    ]},

  { id:'riddle', type:'challenge', weight:7, title:'The Riddle Gate',
    text: S=>`A stone arch, carved with a question in a script that has partially worn away. Enough remains to read.

${S.pucky.name} mouths the words. Something in her face shifts.
"I think I know," she says, "but I don't know if I should say it aloud."

${S.loki.name} reads it twice and starts working through possibilities.`,
    choices:[
      { text:`Trust ${S=>S.pucky.name}'s instinct`, stat:'mag', dc:11, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`${S.pucky.name} speaks her answer — quiet, sure. The arch shimmers and the air on the other side changes. She smiles. "${S.pucky.phrases.success}"`,
          effects:{'pucky.bond':2,'player.mag':1},
          memory:`${S.pucky.name} answered the riddle gate. She was right. She knew she would be.` }),
        lose: S=>({ text:`The arch hums. Wrong. ${S.pucky.name} looks stricken for a moment. "I was sure," she says. "I'm sorry." The gate doesn't punish you — but it doesn't open.`,
          effects:{'pucky.bond':-1,'player.hp':-2},
          memory:`${S.pucky.name} tried to answer the riddle gate and was wrong. She apologized. She didn't need to.` }) },
      { text:`Work through it with ${S=>S.loki.name}`, stat:'wis', dc:12, helper:'loki', helperStat:'wit',
        win: S=>({ text:`${S.loki.name} eliminates possibilities out loud. You follow their logic. Together, you land on it. The gate opens.`,
          effects:{'loki.bond':1,'player.wis':1},
          memory:`Loki and I worked out the riddle together. Logic and patience.` }),
        lose: S=>({ text:`You talk in circles for too long and the gate resets. You find a way around it after an hour.`,
          effects:{'player.hp':-3},
          memory:`Failed the riddle gate. Found another way around, eventually.` }) },
    ]},

  { id:'tunnel', type:'challenge', weight:6, title:'The Collapsed Tunnel',
    text: S=>`The path goes underground. Or it did — the entrance is half-buried, stone fallen inward.

${S.loki.name} walks the perimeter of the collapse immediately, feeling the edge of each stone.
"${S.loki.phrases.craft}"

${S.pucky.name} is already finding rocks to move.`,
    choices:[
      { text:`Help ${S=>S.loki.name} clear it`, stat:'str', dc:10, helper:'loki', helperStat:'craft',
        win: S=>({ text:`Between the two of you — ${S.loki.name} directing, you doing the lifting — the way clears in twenty minutes. Clean work.`,
          effects:{'loki.bond':1,'player.str':1},
          memory:`Cleared the collapsed tunnel with Loki directing. Clean teamwork.` }),
        lose: S=>({ text:`A stone shifts wrong and closes the gap again. You try a second time, with more care. You get through, but bruised.`,
          effects:{'player.hp':-6,'loki.hp':-3},
          memory:`Collapsed tunnel fought back. Took two tries and we were bruised.` }) },
      { text:'Find another way around', stat:'wis', dc:9,
        win: S=>({ text:`You look for fifteen minutes and find a gap between roots — tighter, longer, but passable. ${S.pucky.name} leads the way.`,
          effects:{'player.wis':1,'pucky.bond':1},
          memory:`Went around the collapsed tunnel. Pucky found the gap in the roots.` }),
        lose: S=>({ text:`There isn't a way around — you lose an hour before confirming it. Back to the rubble.`,
          effects:{'player.hp':-3},
          memory:null }) },
    ]},

  { id:'camp', type:'rest', weight:6, title:'The Good Camp',
    text: S=>`You find a place to stop — sheltered, dry, with wood nearby that hasn't quite learned to be wet yet.

${S.loki.name} has a fire going faster than seems reasonable.
${S.pucky.name} sits close to it and says: "${S.pucky.phrases.memory}"

Nobody asks what she means. You all know.`,
    choices:[
      { text:'Rest properly', stat:null,
        win: S=>({ text:`You sleep. Not perfectly — you're in the Grove — but enough. In the morning, everyone is warmer than they were.`,
          effects:{'player.hp':10,'pucky.hp':8,'loki.hp':8,'item':'healers_leaf'},
          memory:`The good camp. Fire, rest, all of us together. Found a healer's leaf in the morning light.` }) },
      { text:'Keep watch so the others can rest', stat:null,
        win: S=>({ text:`You stay awake. Nothing comes. ${S.pucky.name} and ${S.loki.name} sleep deeply. You feel it in your chest, watching them — something quiet and certain.`,
          effects:{'player.hp':3,'pucky.hp':10,'loki.hp':10,'pucky.bond':1,'loki.bond':1},
          memory:`I kept watch so they could sleep. Nothing came. It was enough just to watch them.` }) },
    ]},

  { id:'stars', type:'rest', weight:5, title:'The Night Sky',
    text: S=>`A gap in the canopy opens the sky. Stars — more than usual, or you're just seeing them better.

${S.loki.name} begins naming constellations. Real ones.
${S.pucky.name} begins inventing better ones over the real ones.

You don't have to do anything.`,
    choices:[
      { text:"Listen to Loki's names", stat:null,
        win: S=>({ text:`${S.loki.name} knows all of them and the stories they carry. Afterward, ${S.pucky.name} is quiet for a while. That means she liked it.`,
          effects:{'player.wis':1,'loki.bond':1},
          memory:`Loki named the stars and told their stories. Pucky went quiet after. That meant she liked it.` }) },
      { text:"Help Pucky invent new ones", stat:null,
        win: S=>({ text:`Between you and ${S.pucky.name}, you name fourteen new constellations, including one for ${S.loki.name} that they pretend not to notice. "${S.pucky.phrases.memory}"`,
          effects:{'player.lck':1,'pucky.bond':2},
          memory:`Pucky and I invented fourteen new constellations. One of them was Loki's.` }) },
    ]},

  { id:'pucky_find', type:'event', weight:8, title:"Pucky's Discovery",
    text: S=>`${S.pucky.name} has been quiet for the last half-hour, which you've learned means she's working on something inside herself.

She stops walking.

She opens her hand. In it: something small, strange, clearly alive, and clearly not distressed.
"I found it an hour ago," she says. "I didn't want to lose it by telling you."`,
    choices:[
      { text:'Ask what it is', stat:'mag', dc:10, helper:'pucky', helperStat:'curiosity',
        win: S=>({ text:`You and ${S.pucky.name} examine it together. You don't reach a conclusion — but you understand more than you did. It moves on eventually, as things do.`,
          effects:{'player.mag':1,'pucky.bond':2},
          memory:`Pucky showed me something she'd been carrying for an hour, afraid to tell anyone. We never found out what it was.` }),
        lose: S=>({ text:`You look but it's beyond your frame of reference. ${S.pucky.name} doesn't mind. She sets it down and it goes wherever it was going.`,
          effects:{'pucky.bond':1},
          memory:`Pucky showed me something small and strange. We couldn't name it. She let it go.` }) },
      { text:'Just be glad she showed you', stat:null,
        win: S=>({ text:`"Thank you for showing me," you say. ${S.pucky.name} nods very seriously. It's the right thing to have said.`,
          effects:{'pucky.bond':3,'player.lck':1},
          memory:`Pucky showed me something she'd carried secretly. I said thank you. That was the right answer.` }) },
    ]},

  { id:'loki_builds', type:'event', weight:7, title:'Loki Builds Something',
    text: S=>`${S.loki.name} has been picking things up since this morning — a curved piece of bark, a length of vine, something metallic from the collapsed shed you passed.

Now, sitting apart from the trail, they're making something.

${S.pucky.name} is watching with great attention from three feet away. You come to look.`,
    choices:[
      { text:'Ask what it is', stat:null,
        win: S=>({ text:`"${S.loki.phrases.craft}" says ${S.loki.name} without looking up.\n\nIt's a small device for measuring — something — you aren't sure what. It works perfectly. They hand it to ${S.pucky.name}.`,
          effects:{'loki.bond':2,'pucky.bond':1},
          memory:`Loki built something from found materials and gave it to Pucky. I watched them work.` }) },
      { text:'Help, even if you don\'t know how', stat:'str', dc:9, helper:'loki', helperStat:'craft',
        win: S=>({ text:`${S.loki.name} directs without explaining everything. You hand things as requested. The object takes shape. "${S.loki.phrases.success}"`,
          effects:{'loki.bond':2,'player.str':1},
          memory:`Helped Loki build something without knowing what it was. Just handed things when they asked.` }),
        lose: S=>({ text:`You hand the wrong thing twice. ${S.loki.name} works around you gracefully. The thing still gets made. You feel only slightly useless.`,
          effects:{'loki.bond':1},
          memory:`Tried to help Loki build and mostly got in the way. They didn't mind.` }) },
    ]},

  { id:'merchant', type:'encounter', weight:5, title:'The Wandering Merchant',
    text: S=>{
      const m = getBeingById('merchant');
      const mName = m ? m.name : 'Mara';
      const mEmoji = m ? m.emoji : '🛒';
      const mPhrase = m ? m.phrase : "I have exactly what you need. Usually.";
      return `A cart on an improbable path, piled with things that don't belong in a forest. ${mEmoji} ${mName} is sitting in it, unsurprised to see you.

"${mPhrase}" Not to all of you. To ${S.pucky.name}.

She doesn't seem alarmed by this.`;
    },
    choices:[
      { text:'Browse what they have', stat:'lck', dc:9,
        win: S=>({ text:`Something here is exactly what you needed — you didn't know you needed it until you saw it. You trade something small you'd forgotten you were carrying.`,
          effects:{'player.lck':2,'player.hp':5,'item':'__merchant_random__'},
          memory:`The wandering merchant on the impossible path. They had exactly what we needed.` }),
        lose: S=>({ text:`Nothing fits. The merchant shrugs. "Come back when you know what you're looking for," they say helpfully.`,
          effects:{},
          memory:`The wandering merchant had nothing for us. They said come back when we knew what we needed.` }) },
      { text:`Ask what they wanted with ${S=>S.pucky.name}`, stat:'wis', dc:11,
        win: S=>({ text:`The merchant pauses, then: "She carries something I've been tracking. It's not for me to take. Just wanted to see it." ${S.pucky.name} seems satisfied with this.`,
          effects:{'pucky.bond':1,'player.wis':1},
          memory:`The wandering merchant was tracking something Pucky carries. They didn't try to take it.` }),
        lose: S=>({ text:`The merchant deflects. You learn nothing, but ${S.loki.name} logs it as something to think about later.`,
          effects:{},
          memory:null }) },
    ]},

  { id:'small_fire', type:'rest', weight:5, title:'A Small Fire',
    text: S=>`Nothing is happening. This is, ${S.pucky.name} would say, a gift.

Small fire. The three of you arranged around it without planning how. Insects doing their business nearby.

${S.loki.name} isn't saying anything. That means they're content.`,
    choices:[
      { text:'Stay a while', stat:null,
        win: S=>({ text:`You do. Time passes in the way it only passes when you're not counting it. "${S.pucky.phrases.memory}"`,
          effects:{'player.hp':6,'pucky.hp':5,'loki.hp':5,'pucky.bond':1,'loki.bond':1},
          memory:`A small fire, nothing happening, the three of us together. Pucky said she wanted to remember it.` }) },
    ]},
];

const BOSS = {
  id:'__boss__', type:'boss', title:'The Heart of the Grove',
  text: S=>`The Grove has been paying attention.

You feel it before you see it — a presence, old and large and not unkind, that has been watching your party since the beginning.

${S.pucky.name} takes your hand.
${S.loki.name} takes a breath and holds it.

Something is asking whether you belong here. Not as a challenge. As a genuine question.`,
  choices:[
    { text:'Answer: yes, we belong here', stat:'wis', dc:13, helper:'pucky', helperStat:'heart',
      win: S=>({ text:`The Grove considers. Then: warmth, real and complete, spreading from the center of the clearing outward. It has decided you're right.`,
        effects:{'player.hp':15,'pucky.hp':12,'loki.hp':12,'pucky.bond':2,'loki.bond':2,'player.lck':1},
        memory:`The Grove asked if we belonged here and we said yes. It agreed. I will remember how that warmth felt.` }),
      lose: S=>({ text:`The Grove is unconvinced. Not hostile — but it doesn't yield. You'll have to prove it differently. Your party retreats, shaken but unharmed.`,
        effects:{'player.hp':-5},
        memory:`The Grove asked if we belonged and wasn't sure we did. We'll have to show it.` }) },
    { text:'Answer: we don\'t know yet, but we\'re here', stat:'wis', dc:10,
      win: S=>({ text:`Honesty works where confidence wouldn't have. The Grove settles around you like an exhale. ${S.pucky.name} says: "${S.pucky.phrases.success}"`,
        effects:{'player.hp':10,'pucky.hp':8,'loki.hp':8,'player.wis':1},
        memory:`The Grove asked if we belonged. We said we didn't know yet. That was enough.` }),
      lose: S=>({ text:`The uncertainty carries too much of the wrong kind of weight. The Grove presses back. You'll find your answer in the next chapter.`,
        effects:{'player.hp':-3},
        memory:`Told the Grove we didn't know if we belonged. It wasn't satisfied with that. We'll find out.` }) },
  ],
};

// ── State ─────────────────────────────────────────────────────────────────────

let S;

function defaultWorld(){
  return {
    currentPlace: 'grove',
    places: PLACES_BUILTIN.map(p=>({...p, beings:[...p.beings]})),
    beings: BEINGS_BUILTIN.map(b=>({...b})),
  };
}

function mergeState(saved){
  // Start from defaults and layer in saved values, adding new fields if missing
  const d = JSON.parse(JSON.stringify(DEFAULTS));
  if(!saved) return d;
  const merged = Object.assign({}, d, saved);
  // Always ensure new fields exist
  if(!merged.inventory)     merged.inventory     = [];
  if(!merged.pendingBonus)  merged.pendingBonus  = null;
  if(!merged.world || !merged.world.beings){
    merged.world = defaultWorld();
  }
  return merged;
}

// ── Engine ────────────────────────────────────────────────────────────────────

function roll(sides){ return Math.floor(Math.random()*sides)+1; }

function skillCheck(stat, dc, helper, helperStat){
  const d = roll(20);
  const base = S.player[stat] || 0;
  let bonus = 0;
  if(helper && S[helper]){
    const hStat = S[helper][helperStat] || 0;
    const bond  = S[helper].bond || 0;
    bonus = Math.floor((hStat + bond/2) / 3);
  }
  // Apply pending bonus if it matches stat
  let pendingApplied = 0;
  if(S.pendingBonus && S.pendingBonus.stat === stat){
    pendingApplied = S.pendingBonus.bonus;
    S.pendingBonus = null;
  }
  const total = d + base + bonus + pendingApplied;
  return { d, base, bonus: bonus + pendingApplied, total, dc, pass: total >= dc, pendingApplied };
}

function addItemToInventory(itemId){
  if(itemId === '__merchant_random__'){
    const pool = ['glowstone','loki_notes','ancient_coin'];
    itemId = pool[Math.floor(Math.random()*pool.length)];
  }
  const template = ITEMS[itemId];
  if(!template) return null;
  // Stack consumables/tools if same item already in inventory (for tools, add uses)
  const existing = S.inventory.find(i => i.itemId === itemId);
  if(existing){
    existing.usesLeft = Math.min(existing.usesLeft + (template.uses || 1), (template.uses || 1) * 5);
    return template;
  }
  S.inventory.push({
    itemId,
    name:      template.name,
    emoji:     template.emoji,
    description: template.description,
    effect:    template.effect,
    usesLeft:  template.uses || null,
    usesMax:   template.uses || null,
  });
  return template;
}

function applyEffects(effects){
  if(!effects) return [];
  const pills = [];
  for(const [k,v] of Object.entries(effects)){
    if(k === 'item'){
      const added = addItemToInventory(v);
      if(added) pills.push({ text:`+${added.emoji} ${added.name}`, pos:true, item:true });
      continue;
    }
    const [obj,prop] = k.split('.');
    if(!S[obj]) continue;
    const old = S[obj][prop];
    if(prop === 'hp'){
      S[obj][prop] = Math.min(S[obj].maxHp, Math.max(0, (S[obj][prop]||0)+v));
    } else if(prop === 'bond'){
      S[obj][prop] = Math.min(10, Math.max(0, (S[obj][prop]||0)+v));
    } else if(['str','mag','wis','lck','heart','curiosity','craft','wit'].includes(prop)){
      S[obj][prop] = Math.min(5, Math.max(1, (S[obj][prop]||0)+v));
    }
    if(v !== 0){
      const label = prop==='hp'?'HP':prop==='bond'?`${S[obj].name} bond`:prop;
      const who   = prop==='bond'?'':S[obj].name+' ';
      pills.push({ text:`${v>0?'+':''}${v} ${who}${label}`, pos:v>0 });
    }
  }
  return pills;
}

function addMemory(scene, text){
  if(!text) return;
  S.memories.push({
    id: Date.now(),
    day: S.progress.day,
    chapter: S.progress.chapter,
    scene: scene.title,
    text,
  });
}

function pickScene(){
  if(S.progress.scenesThisChapter >= 5) return BOSS;
  const recent = S.recentScenes || [];
  let pool = POOL.filter(sc => !recent.includes(sc.id));
  if(!pool.length){ S.recentScenes=[]; pool=[...POOL]; }
  const total = pool.reduce((s,sc)=>s+sc.weight,0);
  let r = Math.random()*total;
  for(const sc of pool){ r-=sc.weight; if(r<=0) return sc; }
  return pool[0];
}

function save(){ localStorage.setItem('grove_v1', JSON.stringify(S)); }

function loadState(){
  try{ return JSON.parse(localStorage.getItem('grove_v1')); } catch{ return null; }
}

// ── World Helpers ─────────────────────────────────────────────────────────────

function getBeingById(id){
  return S.world.beings.find(b => b.id === id) || null;
}

function getCurrentPlace(){
  return S.world.places.find(p => p.id === S.world.currentPlace) || S.world.places[0];
}

function getBeingForScene(sceneType){
  if(sceneType !== 'encounter' && sceneType !== 'event') return null;
  const place = getCurrentPlace();
  if(!place || !place.beings || !place.beings.length) return null;
  const ids = place.beings.filter(id => S.world.beings.find(b=>b.id===id));
  if(!ids.length) return null;
  const id = ids[Math.floor(Math.random()*ids.length)];
  return getBeingById(id);
}

// ── Render: Party ─────────────────────────────────────────────────────────────

function hpColor(hp, max){
  const pct = hp/max;
  return pct > 0.5 ? 'var(--pucky)' : pct > 0.25 ? 'var(--gold)' : 'var(--danger)';
}

function renderParty(){
  const chars = [
    { key:'player', cls:'u', hp:S.player.hp, max:S.player.maxHp, name:S.player.name, emoji:S.player.emoji },
    { key:'pucky',  cls:'p', hp:S.pucky.hp,  max:S.pucky.maxHp,  name:S.pucky.name,  emoji:S.pucky.emoji, bond:S.pucky.bond },
    { key:'loki',   cls:'l', hp:S.loki.hp,   max:S.loki.maxHp,   name:S.loki.name,   emoji:S.loki.emoji,  bond:S.loki.bond },
  ];
  document.getElementById('party').innerHTML = chars.map(c=>`
    <div class="char-card">
      <div class="char-emoji">${c.emoji}</div>
      <div class="char-name-sm ${c.cls}">${c.name}</div>
      <div class="hpbar"><div class="hpbar-fill" style="width:${c.hp/c.max*100}%;background:${hpColor(c.hp,c.max)}"></div></div>
      ${c.bond!==undefined?`<div style="font-size:.6em;color:var(--dimmer);margin-top:2px">bond ${c.bond}/10</div>`:''}
    </div>`).join('');

  // Update inventory button badge
  const badge = document.getElementById('inv-badge');
  if(badge) badge.textContent = S.inventory.length || '';

  // Update location hint
  const loc = document.getElementById('location-hint');
  if(loc){
    const place = getCurrentPlace();
    loc.textContent = place ? `📍 ${place.name}` : '';
  }

  // Update pending bonus indicator
  const pb = document.getElementById('pending-bonus');
  if(pb){
    if(S.pendingBonus){
      pb.textContent = `+${S.pendingBonus.bonus} ${S.pendingBonus.stat} ready`;
      pb.style.display = '';
    } else {
      pb.style.display = 'none';
    }
  }
}

// ── Render: Scene ─────────────────────────────────────────────────────────────

function getScene(id){
  if(id==='__intro__') return INTRO;
  if(id==='__boss__')  return BOSS;
  return POOL.find(s=>s.id===id) || INTRO;
}

function renderScene(scene){
  const sa = document.getElementById('scene-area');
  const ca = document.getElementById('choices-area');
  const text = typeof scene.text === 'function' ? scene.text(S) : scene.text;
  sa.innerHTML = `
    <div class="scene-title" style="animation:rise .3s ease">${scene.title}</div>
    <div class="scene-text"  style="animation:rise .35s ease">${text}</div>`;
  ca.innerHTML = scene.choices.map((c,i)=>{
    const choiceText = typeof c.text === 'function' ? c.text(S) : c.text;
    const check = c.stat ? `<div class="check">${c.stat.toUpperCase()} check · DC ${c.dc}${c.helper?` · ${S[c.helper].name} helps`:''}</div>` : '';
    return `<button class="choice-btn" onclick="choose(${i})">${choiceText}${check}</button>`;
  }).join('');
}

function choose(i){
  const scene  = getScene(S.currentSceneId);
  const choice = scene.choices[i];
  const ca     = document.getElementById('choices-area');
  const sa     = document.getElementById('scene-area');

  if(!choice.stat){
    const out = choice.win(S);
    const pills = applyEffects(out.effects);
    if(out.memory) addMemory(scene, out.memory);
    sa.innerHTML += `<div class="outcome-text" style="animation:rise .3s ease">${out.text}</div>
      <div class="effect-pills">${pills.map(p=>`<span class="pill ${p.pos?(p.item?'item':'pos'):'neg'}">${p.text}</span>`).join('')}</div>`;
    ca.innerHTML = `<button class="continue-btn" onclick="advance()">continue →</button>`;
    renderParty();
    save();
    return;
  }

  // Dice roll
  ca.innerHTML = '';
  const faces  = ['⚀','⚁','⚂','⚃','⚄','⚅'];
  sa.innerHTML += `<div class="die-wrap" id="die">⚀</div>`;
  const dieEl  = document.getElementById('die');
  let ticks = 0;
  const iv = setInterval(()=>{
    dieEl.textContent = faces[Math.floor(Math.random()*6)];
    ticks++;
    if(ticks >= 12){
      clearInterval(iv);
      const result = skillCheck(choice.stat, choice.dc, choice.helper, choice.helperStat);
      dieEl.innerHTML = `${faces[result.d-1]}<div class="die-result ${result.pass?'win':'lose'}">${result.pass?'success':'failure'} · rolled ${result.d}+${result.base+result.bonus} vs DC ${result.dc}</div>`;
      const out  = result.pass ? choice.win(S) : (choice.lose ? choice.lose(S) : choice.win(S));
      const pills = applyEffects(out.effects);
      if(out.memory) addMemory(scene, out.memory);
      renderParty();
      sa.innerHTML += `<div class="outcome-text" style="animation:rise .3s ease">${out.text}</div>
        <div class="effect-pills">${pills.map(p=>`<span class="pill ${p.pos?(p.item?'item':'pos'):'neg'}">${p.text}</span>`).join('')}</div>`;
      ca.innerHTML = `<button class="continue-btn" onclick="advance()">continue →</button>`;
      save();
      const scr = document.getElementById('scene-area');
      setTimeout(()=>scr.scrollTop=scr.scrollHeight, 50);
    }
  }, 60);
}

function advance(){
  const wasBoss = S.currentSceneId === '__boss__';
  if(wasBoss){
    S.progress.chapter++;
    S.progress.scenesThisChapter=0;
    S.progress.day++;
  } else {
    S.progress.scenesThisChapter++;
    S.progress.totalScenes++;
    if(!S.recentScenes) S.recentScenes=[];
    S.recentScenes.push(S.currentSceneId);
    if(S.recentScenes.length > 5) S.recentScenes.shift();
  }
  const next = pickScene();
  S.currentSceneId = next.id;
  save();
  renderParty();
  renderScene(next);
  document.getElementById('scene-area').scrollTop = 0;
}

// ── Inventory ─────────────────────────────────────────────────────────────────

function openInventory(){
  document.getElementById('inv-overlay').classList.add('on');
  renderInventoryPanel();
}

function closeInventory(){
  document.getElementById('inv-overlay').classList.remove('on');
}

function renderInventoryPanel(){
  const list = document.getElementById('inv-list');
  if(!S.inventory.length){
    list.innerHTML = '<div class="inv-empty">nothing carried</div>';
    return;
  }
  list.innerHTML = S.inventory.map((item, idx) => {
    const usesLabel = item.usesLeft !== null
      ? `<div class="item-uses">${item.usesLeft} use${item.usesLeft===1?'':'s'} left</div>` : '';
    const canUse = item.usesLeft === null || item.usesLeft > 0;
    const useBtn = canUse
      ? `<button class="item-use-btn" onclick="useItem(${idx})">use</button>` : '';
    return `<div class="item-row">
      <div class="item-emoji">${item.emoji}</div>
      <div class="item-info">
        <div class="item-name">${item.name}</div>
        <div class="item-desc">${item.description}</div>
        ${usesLabel}
      </div>
      ${useBtn}
    </div>`;
  }).join('');
}

function useItem(idx){
  const item = S.inventory[idx];
  if(!item) return;
  const eff = item.effect;
  let msg = '';

  if(eff.hp){
    // restore HP to player
    S.player.hp = Math.min(S.player.maxHp, S.player.hp + eff.hp);
    msg = `${item.emoji} Restored ${eff.hp} HP.`;
  } else if(eff.allHp){
    S.player.hp  = Math.min(S.player.maxHp,  S.player.hp  + eff.allHp);
    S.pucky.hp   = Math.min(S.pucky.maxHp,   S.pucky.hp   + eff.allHp);
    S.loki.hp    = Math.min(S.loki.maxHp,    S.loki.hp    + eff.allHp);
    msg = `${item.emoji} Restored ${eff.allHp} HP to everyone.`;
  } else if(eff.stat){
    S.pendingBonus = { stat: eff.stat, bonus: eff.bonus };
    msg = `${item.emoji} +${eff.bonus} ${eff.stat} on next ${eff.stat} check.`;
  } else if(eff.reroll){
    S.pendingBonus = { stat: '__reroll__', bonus: 0, reroll: true };
    msg = `${item.emoji} Will re-roll on next failure.`;
  }

  // Decrement uses or remove
  if(item.usesLeft !== null){
    item.usesLeft--;
    if(item.usesLeft <= 0){
      S.inventory.splice(idx, 1);
    }
  }

  save();
  renderParty();
  renderInventoryPanel();
  if(msg){
    // Flash a small message
    const head = document.querySelector('.inv-panel-head h2');
    if(head){ const orig = head.textContent; head.textContent = msg; setTimeout(()=>head.textContent=orig, 2000); }
  }
}

// ── Companions Tab ────────────────────────────────────────────────────────────

const EMOJIS = ['🌿','🌱','🍀','🌸','🌙','⭐','🔮','🦊','🐺','🦉','🐸','🐝','🦋',
                '🔧','⚒️','🛡️','⚔️','🌊','🔥','❄️','🌈','🍄','🐉','🦌','🐇'];

function statEditor(charKey, statKey, label, color){
  const val = S[charKey][statKey];
  return `<div class="stat-row">
    <label style="color:${color||'var(--dim)'}">${label}</label>
    <div class="stat-controls">
      <button class="stat-btn" onclick="adjStat('${charKey}','${statKey}',-1)">−</button>
      <span class="stat-val" id="sv-${charKey}-${statKey}">${val}</span>
      <button class="stat-btn" onclick="adjStat('${charKey}','${statKey}',1)">+</button>
    </div>
  </div>`;
}

function adjStat(charKey, statKey, delta){
  S[charKey][statKey] = Math.min(5, Math.max(1, S[charKey][statKey]+delta));
  document.getElementById(`sv-${charKey}-${statKey}`).textContent = S[charKey][statKey];
  save();
}

function setName(charKey, val){ S[charKey].name=val; save(); renderParty(); }
function setEmoji(charKey, val){ S[charKey].emoji=val; save(); renderParty(); }
function setPhrase(charKey, phraseKey, val){ S[charKey].phrases[phraseKey]=val; save(); }

function showEmojiPicker(charKey){
  document.getElementById(`ep-${charKey}`).classList.toggle('on');
}

function pickEmoji(charKey, emoji){
  S[charKey].emoji = emoji;
  document.getElementById(`einput-${charKey}`).value = emoji;
  document.getElementById(`ep-${charKey}`).classList.remove('on');
  save(); renderParty();
}

function renderCompanions(){
  const comp = document.getElementById('comp');
  const chars = [
    { key:'player', cls:'u', label:'You', stats:[['str','STR'],['mag','MAG'],['wis','WIS'],['lck','LCK']], phraseKeys:[] },
    { key:'pucky',  cls:'p', label:S.pucky.name, stats:[['heart','HEART'],['curiosity','CURIOSITY']], phraseKeys:['greeting','curious','success','failure','scared','memory'] },
    { key:'loki',   cls:'l', label:S.loki.name,  stats:[['craft','CRAFT'],['wit','WIT']], phraseKeys:['greeting','plan','success','failure','craft','memory'] },
  ];

  comp.innerHTML = chars.map(c=>`
  <div class="comp-card">
    <div class="comp-header">
      <div class="comp-emoji-big" onclick="showEmojiPicker('${c.key}')">${S[c.key].emoji}</div>
      <div class="comp-title">
        <h3 class="${c.cls}">${c.label}</h3>
        ${c.key!=='player'?`<div class="bond-bar"><div class="bond-fill" style="width:${S[c.key].bond*10}%"></div></div>`:''}
      </div>
    </div>
    <div class="emoji-picker" id="ep-${c.key}">
      ${EMOJIS.map(e=>`<span class="epick" onclick="pickEmoji('${c.key}','${e}')">${e}</span>`).join('')}
    </div>
    <div class="field">
      <label>Name</label>
      <input id="einput-${c.key}" value="${S[c.key].name}" oninput="setName('${c.key}',this.value)">
    </div>
    <div class="field">
      <label>Emoji</label>
      <input value="${S[c.key].emoji}" oninput="setEmoji('${c.key}',this.value)" maxlength="2" style="width:60px">
    </div>
    <div class="stats-grid">
      ${c.stats.map(([sk,sl])=>statEditor(c.key,sk,sl)).join('')}
    </div>
    ${c.phraseKeys.length?`<div class="phrases-section">
      <details>
        <summary>phrases</summary>
        <div class="phrases-grid">
          ${c.phraseKeys.map(pk=>`<div class="phrase-row">
            <div class="phrase-label">${pk}</div>
            <input value="${(S[c.key].phrases[pk]||'').replace(/"/g,'&quot;')}" oninput="setPhrase('${c.key}','${pk}',this.value)">
          </div>`).join('')}
        </div>
      </details>
    </div>`:''}
  </div>`).join('');
}

// ── World Tab ─────────────────────────────────────────────────────────────────

let worldSubtab = 'places';
// Track which cards have edit forms open: Map of id -> true
const worldEditOpen = {};

function setWorldSubtab(tab){
  worldSubtab = tab;
  document.querySelectorAll('.world-subtab').forEach(el=>{
    el.classList.toggle('on', el.dataset.tab === tab);
  });
  renderWorldContent();
}

function renderWorld(){
  renderWorldContent();
}

function beingTypeBadge(type){
  const cls = ['tavern','merchant','spirit','creature','builder'].includes(type) ? type : 'custom';
  return `<span class="being-type-badge badge-${cls}">${type}</span>`;
}

function renderWorldContent(){
  const wc = document.getElementById('world-content');
  if(worldSubtab === 'places'){
    wc.innerHTML = renderPlaces();
  } else {
    wc.innerHTML = renderBeings();
  }
}

function renderPlaces(){
  const places = S.world.places;
  const cards = places.map((place, idx) => {
    const isCurrent = place.id === S.world.currentPlace;
    const beingNames = (place.beings || []).map(bid => {
      const b = getBeingById(bid);
      return b ? `${b.emoji} ${b.name}` : null;
    }).filter(Boolean).join(', ');

    const travelBtn = isCurrent
      ? `<button class="place-travel-btn here" disabled>here now</button>`
      : `<button class="place-travel-btn" onclick="travelTo('${place.id}')">travel here</button>`;

    const editBtn = `<button class="world-action-btn" onclick="togglePlaceEdit('${place.id}')">edit</button>`;
    const delBtn  = place.custom ? `<button class="world-action-btn del" onclick="deletePlace('${place.id}')">delete</button>` : '';

    const editForm = worldEditOpen[place.id] ? `
      <div class="place-edit-form">
        <div class="world-field">
          <label>Name</label>
          <input value="${esc(place.name)}" oninput="updatePlace('${place.id}','name',this.value)">
        </div>
        <div class="world-field">
          <label>Emoji</label>
          <input value="${esc(place.emoji)}" oninput="updatePlace('${place.id}','emoji',this.value)" style="width:60px">
        </div>
        <div class="world-field">
          <label>Description</label>
          <textarea rows="2" oninput="updatePlace('${place.id}','description',this.value)">${esc(place.description)}</textarea>
        </div>
      </div>` : '';

    return `<div class="place-card${isCurrent?' current':''}">
      <div class="place-card-head">
        <div class="place-emoji">${place.emoji}</div>
        <div class="place-meta">
          <div class="place-name">${isCurrent?'<div class="place-current-dot"></div>':''}${esc(place.name)}</div>
          <div class="place-type">${place.type}</div>
        </div>
      </div>
      <div class="place-desc">${esc(place.description)}</div>
      ${beingNames ? `<div class="place-beings-list">beings here: ${beingNames}</div>` : ''}
      <div class="place-actions">
        ${travelBtn}${editBtn}${delBtn}
      </div>
      ${editForm}
    </div>`;
  }).join('');

  return `<div class="place-grid">${cards}</div>
    <button class="world-add-btn" onclick="addPlace()">+ create place</button>`;
}

function renderBeings(){
  const beings = S.world.beings;
  const cards = beings.map((being) => {
    const editBtn = `<button class="world-action-btn" onclick="toggleBeingEdit('${being.id}')">edit</button>`;
    const delBtn  = being.custom ? `<button class="world-action-btn del" onclick="deleteBeing('${being.id}')">delete</button>` : '';

    const editForm = worldEditOpen['being_'+being.id] ? `
      <div class="being-edit-form">
        <div class="world-field">
          <label>Name</label>
          <input value="${esc(being.name)}" oninput="updateBeing('${being.id}','name',this.value)">
        </div>
        <div class="world-field">
          <label>Emoji</label>
          <input value="${esc(being.emoji)}" oninput="updateBeing('${being.id}','emoji',this.value)" style="width:60px">
        </div>
        <div class="world-field">
          <label>Description</label>
          <textarea rows="2" oninput="updateBeing('${being.id}','description',this.value)">${esc(being.description)}</textarea>
        </div>
        <div class="world-field">
          <label>Phrase</label>
          <input value="${esc(being.phrase)}" oninput="updateBeing('${being.id}','phrase',this.value)">
        </div>
      </div>` : '';

    return `<div class="being-card">
      <div class="being-head">
        <div class="being-emoji">${being.emoji}</div>
        <div class="being-meta">
          <div class="being-name">${esc(being.name)}</div>
          ${beingTypeBadge(being.type)}
        </div>
      </div>
      <div class="being-desc">${esc(being.description)}</div>
      <div class="being-phrase">"${esc(being.phrase)}"</div>
      <div class="being-actions">
        ${editBtn}${delBtn}
      </div>
      ${editForm}
    </div>`;
  }).join('');

  return `<div class="being-list">${cards}</div>
    <button class="world-add-btn" onclick="addBeing()">+ create being</button>`;
}

function esc(str){ return String(str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

function travelTo(placeId){
  S.world.currentPlace = placeId;
  save();
  renderParty();
  renderWorldContent();
}

function togglePlaceEdit(placeId){
  worldEditOpen[placeId] = !worldEditOpen[placeId];
  renderWorldContent();
}

function toggleBeingEdit(beingId){
  const key = 'being_'+beingId;
  worldEditOpen[key] = !worldEditOpen[key];
  renderWorldContent();
}

function updatePlace(placeId, field, value){
  const place = S.world.places.find(p=>p.id===placeId);
  if(place){ place[field] = value; save(); }
  // Re-render party to update location hint if name changed
  if(field === 'name') renderParty();
}

function updateBeing(beingId, field, value){
  const being = S.world.beings.find(b=>b.id===beingId);
  if(being){ being[field] = value; save(); }
}

function addPlace(){
  const id = 'custom_place_' + Date.now();
  S.world.places.push({ id, name:'New Place', emoji:'🗺️', type:'custom', description:'A place to describe.', beings:[], custom:true });
  worldEditOpen[id] = true;
  save();
  renderWorldContent();
}

function deletePlace(placeId){
  S.world.places = S.world.places.filter(p=>p.id!==placeId);
  if(S.world.currentPlace === placeId) S.world.currentPlace = 'grove';
  save();
  renderWorldContent();
}

function addBeing(){
  const id = 'custom_being_' + Date.now();
  S.world.beings.push({ id, name:'New Being', emoji:'✨', type:'custom', description:'A being to describe.', phrase:'...', custom:true });
  worldEditOpen['being_'+id] = true;
  save();
  renderWorldContent();
}

function deleteBeing(beingId){
  S.world.beings = S.world.beings.filter(b=>b.id!==beingId);
  save();
  renderWorldContent();
}

// ── Memories Tab ──────────────────────────────────────────────────────────────

function renderMemories(){
  const mem = document.getElementById('mem');
  if(!S.memories.length){
    mem.innerHTML = `<div class="mem-header"><h2>memories</h2></div><div class="mem-empty">nothing yet</div>`;
    return;
  }
  const byChapter = {};
  for(const m of S.memories){
    if(!byChapter[m.chapter]) byChapter[m.chapter]=[]; byChapter[m.chapter].push(m);
  }
  mem.innerHTML = `
    <div class="mem-header">
      <h2>memories</h2>
      <button class="dl-btn" onclick="downloadMemories()">save .txt</button>
    </div>
    ${Object.entries(byChapter).reverse().map(([ch,mems])=>`
      <div class="mem-chapter">chapter ${ch} · day ${mems[0].day}</div>
      ${mems.map(m=>`
        <div class="mem-entry">
          <div class="mem-scene">${m.scene}</div>
          <div class="mem-text">${m.text}</div>
        </div>`).join('')}
    `).join('')}`;
}

function downloadMemories(){
  const lines = Object.entries(
    S.memories.reduce((acc,m)=>{(acc[m.chapter]=acc[m.chapter]||[]).push(m);return acc;},{})
  ).map(([ch,mems])=>`── Chapter ${ch} ──\n\n`+mems.map(m=>`${m.scene}\n${m.text}`).join('\n\n')).join('\n\n\n');
  const blob = new Blob([`${S.pucky.name} & ${S.loki.name} — Memories from the Grove\n\n${lines}`],{type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download=`${S.pucky.name}_memories.txt`; a.click();
  URL.revokeObjectURL(a.href);
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

function setTab(tab){
  ['adv','world','comp','mem'].forEach(t=>{
    const el = document.getElementById(t);
    const tabEl = document.getElementById(`tab-${t}`);
    if(el) el.classList.toggle('on', t===tab);
    if(tabEl) tabEl.classList.toggle('on', t===tab);
  });
  if(tab==='comp')  renderCompanions();
  if(tab==='mem')   renderMemories();
  if(tab==='world') renderWorld();
}

// ── Apple Touch Icon ──────────────────────────────────────────────────────────

(function(){
  const sz=180, c=document.createElement('canvas'); c.width=c.height=sz;
  const ctx=c.getContext('2d'), s=sz/512;
  ctx.fillStyle='#0a0e14'; ctx.fillRect(0,0,sz,sz);
  function glow(cx,cy,col){
    const g=ctx.createRadialGradient(cx,cy,0,cx,cy,110*s);
    g.addColorStop(0,col+'55'); g.addColorStop(1,col+'00');
    ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,110*s,0,Math.PI*2); ctx.fill();
  }
  function orb(cx,cy,l,m,d){
    const g=ctx.createRadialGradient(cx-10*s,cy-12*s,0,cx,cy,82*s);
    g.addColorStop(0,l); g.addColorStop(.48,m); g.addColorStop(1,d);
    ctx.fillStyle=g; ctx.beginPath(); ctx.arc(cx,cy,82*s,0,Math.PI*2); ctx.fill();
  }
  glow(168*s,256*s,'#68c88e'); glow(344*s,256*s,'#c8956a');
  orb(168*s,256*s,'#c0f8e0','#68c88e','#1a3f28');
  orb(344*s,256*s,'#f8e8c0','#c8956a','#3f2010');
  const lk=document.createElement('link'); lk.rel='apple-touch-icon';
  lk.href=c.toDataURL('image/png'); document.head.appendChild(lk);
})();

if('serviceWorker' in navigator) navigator.serviceWorker.register('./game-sw.js');

// ── Init ──────────────────────────────────────────────────────────────────────

S = mergeState(loadState());
// Ensure world is populated (for old saves or fresh starts)
if(!S.world || !S.world.beings){
  S.world = defaultWorld();
}

renderParty();
renderScene(getScene(S.currentSceneId));
