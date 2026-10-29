# -*- coding: utf-8 -*-
# SUSFS 6.12 rollup 老形态补守卫 (2026-10-29)
# 背景：susfs4ksu gki-android16-6.12 分支 10-18 rebase 到 6.12.92 后，task_mmu.c 的
#   SUS_MAP rollup 两处守卫(#5 循环头 goto+label、#6 Case-4 括号块)按 92 重构形态写上下文；
#   6.12.23~69 这些老 tag 仍是老形态 → 两个 hunk 静默失配(.rej 被收集但不阻断)，
#   结果 smaps_rollup 不再隐藏 sus 映射 VMA。本脚本在老形态上补齐等价守卫。
# 语义与旧 pin(acb92d4) 的 Hunk#5/#6 产物逐字一致，保证换 pin 前后隐藏行为不变。
# 用法：主补丁打完紧接着跑；仅 android16-6.12 且 sub<=69 的树会命中(自带形态自检)。
import os, re, sys

root = './' if os.path.isdir('./fs/proc') else './common/'
p = root + 'fs/proc/task_mmu.c'
rej = root + 'fs/proc/task_mmu.c.rej'
if not os.path.exists(p):
    print('skip: 找不到', p)
    raise SystemExit

src = open(p, encoding='utf-8', errors='ignore').read()
i = src.find('static int show_smaps_rollup(')
if i < 0:
    print('skip: 无 show_smaps_rollup')
    raise SystemExit
j = src.find('\nstatic ', i + 10)
fn = src[i:j if j > 0 else len(src)]

if 'SUSFS_IS_INODE_SUS_MAP' in fn:
    print('rollup 已含 SUS_MAP 守卫, skip（新形态树）')
    if os.path.exists(rej):
        os.remove(rej)
        print('removed', rej)
    raise SystemExit

changed = 0

# --- 处 1: 循环头 gather + 尾随 label（老 pin Hunk#5 的产物形态） ---
m1 = re.search(r'(\t+)smap_gather_stats\(vma, &mss, 0\);\n(\t+)last_vma_end = vma->vm_end;', fn)
if m1:
    T = m1.group(1)
    repl = (T + '#ifdef CONFIG_KSU_SUSFS_SUS_MAP' + '\n'
            + T + '\tif (vma->vm_file && SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))' + '\n'
            + T + '\t\tgoto bypass_orig_flow;' + '\n'
            + T + '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP' + '\n'
            + m1.group(0) + '\n'
            + T + '#ifdef CONFIG_KSU_SUSFS_SUS_MAP' + '\n'
            + 'bypass_orig_flow:' + '\n'
            + T + '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP')
    fn = fn.replace(m1.group(0), repl, 1)
    changed += 1
    print('处1 循环头守卫已补')
else:
    print('处1 形态未匹配(可能该 tag 已重构), 保留 .rej 待人工审查')

# --- 处 2: Case-4 括号块（老 pin Hunk#6 的产物形态） ---
m2 = re.search(r'(if \(vma->vm_end > last_vma_end\) \{\n)(\t+)'
               r'(smap_gather_stats\(vma, &mss, last_vma_end\);\n\t+last_vma_end = vma->vm_end;\n)'
               r'(\t+\})', fn)
if m2:
    T = m2.group(2)
    repl = (m2.group(1)
            + T + '#ifdef CONFIG_KSU_SUSFS_SUS_MAP' + '\n'
            + T + '\tif (!vma->vm_file || !(SUSFS_IS_INODE_SUS_MAP(file_inode(vma->vm_file)))) {' + '\n'
            + T + '\t\t\tsmap_gather_stats(vma, &mss, last_vma_end);' + '\n'
            + T + '\t\t\tlast_vma_end = vma->vm_end;' + '\n'
            + T + '\t\t}' + '\n'
            + T + '#else' + '\n'
            + m2.group(3)
            + T + '#endif // #ifdef CONFIG_KSU_SUSFS_SUS_MAP' + '\n'
            + m2.group(4))
    fn = fn.replace(m2.group(0), repl, 1)
    changed += 1
    print('处2 Case-4 守卫已补')
else:
    print('处2 形态未匹配(可能无括号形态), 保留 .rej 待人工审查')

if changed:
    src = src[:i] + fn + (src[j:] if j > 0 else '')
    open(p, 'w', encoding='utf-8', newline='').write(src)
    if os.path.exists(rej):
        # 仅当两处都补齐才清 .rej；否则留着给门禁/人工看
        if changed == 2:
            os.remove(rej)
            print('两处齐 → removed', rej)
        else:
            print('只补齐 1 处 → .rej 保留')
    print(f'6.12 rollup 老形态补守卫完成 ({changed}/2)')
else:
    print('WARN: 两处都没匹配上, .rej 保留待人工审查')
