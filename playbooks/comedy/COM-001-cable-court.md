# COM-001 · 数据线法庭

- 生成验证：**待验证，未生成成片**
- 带货效果：未测
- 创建日期：2026-11-03
- 类型：搞笑带货 / 拟人 / 严肃处理小麻烦
- 假设商品：可重复开合的理线带；以实物结构与用法为准
- 设计：约 24 秒，4 镜各约 6 秒，竖屏
- 模型 / 参数 / 任务 ID / 实验 / 成片：尚未选择或产生

## 创意机制

一团打结的数据线被当作「每天制造混乱的被告」，主角一本正经开庭。判决不是魔法消失，而是按实际用法用理线带固定整理好的线，最后把它送进标着收纳格的区域。笑点来自对小麻烦的过度认真。

商品负责真实解决线缆收纳，法庭只是表现方式。避免让商品自动解开死结，或让线无接触变整齐。

## 素材

- `PRODUCT_REF`：同一变体理线带、尺寸、打开与闭合状态、真实用法图。
- `ACTOR_REF`：同一成人角色，深色外套，表情严肃。
- `SCENE_REF`：桌面玩具法庭布局，法槌、左侧线团、右侧收纳格。
- `COILED_CABLE_REF`：手工整理好的线圈，用于功能演示镜头。
- 素材均待提供，占位符不是平台语法。假如实物不能包住该线圈，需更换示例道具。

## 分镜与提示词

### 镜头 1：荒唐但严肃的开庭，约 6 秒

```text
Vertical medium close-up of the adult in ACTOR_REF seated at the small
tabletop courtroom from SCENE_REF. Dark jacket, solemn expression, warm
indoor lighting. A tangled cable sits on the left side of the table like
an accused object. The adult lifts a small wooden gavel and taps the block
once, then looks directly at the cable. Static camera, restrained deadpan
comedy. The cable remains an ordinary inanimate object. No dialogue or
generated text; add courtroom sound and voice in post.
```

后期配音：`“You are charged with daily desk chaos.”`

### 镜头 2：被告特写，约 6 秒

```text
Vertical close-up of the tangled cable in the same tabletop courtroom.
Match the cable and its position in SCENE_REF. Slow single camera push-in.
The cable does not move, speak, grow eyes or change shape. Hold the absurdly
serious composition for a reaction beat. Warm indoor light, realistic cable
texture. No people in this shot, no generated text, no dialogue.
```

后期音效：短暂停顿后，法官画外音 `“Again.”`

### 镜头 3：真实商品动作，约 6 秒

```text
Vertical fixed close-up on the courtroom table. The cable is now neatly
coiled as shown in COILED_CABLE_REF; it was arranged before this shot.
The exact reusable cable tie from PRODUCT_REF is already positioned around
the coil in its real open state. One adult right hand closes the tie using
the documented real mechanism. Show the contact point clearly and hold the
closed result. Preserve product size, color and fastening design. No magic
untangling, no extra fingers, no captions or dialogue.
```

后期配音：`“Sentenced to staying organized.”`

### 镜头 4：结尾回扣，约 6 秒

```text
Vertical medium close view of the same tabletop courtroom. The adult in
ACTOR_REF keeps the same dark jacket and serious face. The coiled cable,
secured by the exact PRODUCT_REF tie, rests in the right-hand storage
compartment. The adult gives one tiny approving nod, then gently slides
the compartment toward camera without covering the tie. Static framing,
warm light, realistic motion. No generated text or dialogue. End with
the product and secured cable plainly visible.
```

后期字幕可写 `“Case closed.”`，不让模型生成牌匾文字。

## 制作计划与测试点

开合结构难生成时，使用真实操作素材做镜头 3，再匹配其余生成镜头；如采用合成需记录。先测试关键功能镜头，再做喜剧镜头。检查没有旁白时是否仍能理解冲突，以及观众是否能辨认商品。尚无证据证明此创意能提升观看或转化。
