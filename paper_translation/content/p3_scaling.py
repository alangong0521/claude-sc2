"""Paper 3: Scaling Laws for Neural Language Models
Kaplan et al. (OpenAI, 2020) - arXiv:2001.08361
Full bilingual (English / 中文) content for main body + key appendix tables.
"""
from reportlab.lib.units import cm

PAPER3 = {
    "title_for_pdf": "Scaling Laws for Neural Language Models (EN/ZH)",
    "content": [
        {"type": "title_pair",
         "en": "Scaling Laws for Neural Language Models",
         "zh": "神经语言模型的尺度定律"},

        {"type": "authors_pair",
         "en": "Jared Kaplan · Sam McCandlish · Tom Henighan · Tom B. Brown · "
               "Benjamin Chess · Rewon Child · Scott Gray · Alec Radford · "
               "Jeffrey Wu · Dario Amodei<br/>"
               "Johns Hopkins University &nbsp; / &nbsp; OpenAI",
         "zh": "贾里德·卡普兰 · 萨姆·麦坎德利斯 · 汤姆·赫尼甘 · 汤姆·B·布朗 · "
                "本杰明·切斯 · 雷翁·柴尔德 · 斯科特·格雷 · 亚历克·拉德福德 · "
                "杰弗里·吴 · 达里奥·阿莫代i(OpenAI 等)"},

        {"type": "meta", "text":
            "arXiv:2001.08361 [cs.LG]  |  Preprint, January 2020"},

        {"type": "spacer", "size": 8},

        {"type": "abstract_title", "text": "Abstract | 摘要"},

        {"type": "p_abstract", "en":
            "We study empirical scaling laws for language model performance on the cross-entropy "
            "loss. The loss scales as a power-law with model size, dataset size, and the amount "
            "of compute used for training, with some trends spanning more than seven orders of "
            "magnitude. Other architectural details such as network width or depth have minimal "
            "effects within a wide range. Simple equations govern the dependence of overfitting "
            "on model/dataset size and the dependence of training speed on model size. These "
            "relationships allow us to determine the optimal allocation of a fixed compute "
            "budget. Larger models are significantly more sample-efficient, such that "
            "optimally compute-efficient training involves training very large models on a "
            "relatively modest amount of data and stopping significantly before convergence.",
         "zh":
            "我们研究了语言模型性能(交叉熵损失)随尺度变化的实证定律。损失随模型规模、数据 "
            "集规模以及训练所用的算力呈幂律关系,部分趋势跨越了超过七个数量级。在较宽的范围 "
            "内,网络宽度或深度等其他架构细节的影响很小。简单的方程即可刻画过拟合对模型/数 "
            "据规模的依赖,以及训练速度对模型规模的依赖。这些关系使我们能够确定在固定算力预 "
            "算下的最优分配方式。更大的模型显著更加样本高效,因此,算力最优的训练方式是:用 "
            "相对适量的数据去训练一个非常大的模型,并在远未收敛时就提前停止训练。"},

        {"type": "h1", "text": "1. Introduction | 引言"},

        {"type": "p", "en":
            "Language provides a natural domain for the study of artificial intelligence, as "
            "the vast majority of reasoning tasks can be efficiently expressed and evaluated in "
            "language, and the world's text provides a wealth of data for unsupervised learning "
            "via generative modeling. Deep learning has recently seen rapid progress in language "
            "modeling, with state of the art models approaching human-level performance on "
            "many specific tasks, including the composition of coherent multi-paragraph prompted "
            "text samples.",
         "zh":
            "语言是研究人工智能的一个自然领域——绝大多数推理任务都能被高效地用语言表达与评 "
            "估,而世界上的文本为通过生成式建模进行无监督学习提供了海量数据。近年来,深度 "
            "学习在语言建模上取得了飞速进展,最先进的方法已在许多特定任务上接近人类水平, "
            "包括生成连贯的多段提示文本。"},

        {"type": "p", "en":
            "One might expect language modeling performance to depend on model architecture, "
            "the size of neural models, the computing power used to train them, and the data "
            "available for this training process. In this work we will empirically investigate "
            "the dependence of language modeling loss on all of these factors, focusing on the "
            "Transformer architecture. The high ceiling and low floor for performance on "
            "language tasks allows us to study trends over more than seven orders of magnitude "
            "in scale.",
         "zh":
            "人们可能预期,语言建模的性能会依赖于模型架构、神经网络的规模、训练所用的算力, "
            "以及可用于训练的数据。在本文中,我们将实证地研究语言建模损失对所有这些因素的依 "
            "赖,并聚焦于 Transformer 架构。语言任务性能的高上限和低下限,使我们能够在超过 "
            "七个数量级的尺度上研究其趋势。"},

        {"type": "p", "en":
            "Throughout we will observe precise power-law scalings for performance as a "
            "function of training time, context length, dataset size, model size, and compute "
            "budget.",
         "zh":
            "在本文中,我们将观察到:性能作为训练时间、上下文长度、数据集规模、模型规模和算 "
            "力预算的函数,呈现精确的幂律关系。"},

        {"type": "h2", "text": "1.1 Summary | 主要结论概述"},

        {"type": "p", "en":
            "Our key findings for Transformer language models are as follows.",
         "zh": "本文关于 Transformer 语言模型的关键发现如下。"},

        {"type": "p", "en":
            "Performance depends strongly on scale, weakly on model shape. Model performance "
            "depends most strongly on scale, which consists of three factors: the number of "
            "model parameters N (excluding embeddings), the size of the dataset D, and the "
            "amount of compute C used for training. Within reasonable limits, performance "
            "depends very weakly on other architectural hyperparameters such as depth vs. width.",
         "zh":
            "性能强烈依赖于尺度,微弱依赖于模型形状。模型性能最强烈地依赖于尺度,它由三个 "
            "因素组成:模型参数量 N(不含嵌入)、数据集规模 D,以及训练所用算力 C。在合理 "
            "范围内,深度与宽度等其它架构超参数对性能的影响非常微弱。"},

        {"type": "p", "en":
            "Smooth power laws. Performance has a power-law relationship with each of the three "
            "scale factors N, D, C when not bottlenecked by the other two, with trends spanning "
            "more than six orders of magnitude. We observe no signs of deviation from these "
            "trends on the upper end, though performance must flatten out eventually before "
            "reaching zero loss.",
         "zh":
            "平滑的幂律。在不因其它两者而成为瓶颈的前提下,性能与 N、D、C 三个尺度因子各自呈 "
            "幂律关系,趋势跨越超过六个数量级。在上限附近,我们没有观察到这些趋势出现偏离的 "
            "迹象,尽管性能必然会在损失为零之前趋于平缓。"},

        {"type": "p", "en":
            "Universality of overfitting. Performance improves predictably as long as we scale "
            "up N and D in tandem, but enters a regime of diminishing returns if either N or D "
            "is held fixed while the other increases. The performance penalty depends "
            "predictably on the ratio N^{0.74} / D, meaning that every time we increase the "
            "model size 8×, we only need to increase the data by roughly 5× to avoid a penalty.",
         "zh":
            "过拟合的普适性。只要 N 与 D 同步增大,性能就会可预测地提升;但若其中一个固定而 "
            "另一个增大,则会进入收益递减的区域。性能惩罚可由比值 N^{0.74} / D 可预测地刻画, "
            "这意味着:每当模型规模扩大 8 倍,我们只需将数据扩大约 5 倍即可避免过拟合惩罚。"},

        {"type": "p", "en":
            "Universality of training. Training curves follow predictable power-laws whose "
            "parameters are roughly independent of the model size. By extrapolating the early "
            "part of a training curve, we can roughly predict the loss that would be achieved "
            "if we trained for much longer.",
         "zh":
            "训练过程的普适性。训练曲线遵循可预测的幂律,其参数与模型规模大致无关。通过对训 "
            "练曲线早期部分进行外推,我们可以粗略预测在更长时间训练下能达到的损失。"},

        {"type": "p", "en":
            "Transfer improves with test performance. When we evaluate models on text with a "
            "different distribution than they were trained on, the results are strongly "
            "correlated to those on the training validation set with a roughly constant offset "
            "in the loss — in other words, transfer to a different distribution incurs a "
            "constant penalty but otherwise improves roughly in line with performance on the "
            "training set.",
         "zh":
            "迁移随测试性能提升而提升。当我们在与训练数据分布不同的文本上评估模型时,结果与 "
            "训练验证集上的结果强相关,损失的偏移大致为常数——换言之,迁移到不同分布会带来 "
            "一个常数惩罚,除此之外,其提升大致与训练集上的性能同步。"},

        {"type": "p", "en":
            "Sample efficiency. Large models are more sample-efficient than small models, "
            "reaching the same level of performance with fewer optimization steps and using "
            "fewer data points.",
         "zh":
            "样本效率。更大的模型比小模型更加样本高效:它们可以用更少的优化步数、更少的数据 "
            "点达到相同的性能水平。"},

        {"type": "p", "en":
            "Convergence is inefficient. When working within a fixed compute budget C but "
            "without any other restrictions on the model size N or available data D, we attain "
            "optimal performance by training very large models and stopping significantly short "
            "of convergence. Maximally compute-efficient training would therefore be far more "
            "sample efficient than one might expect based on training small models to "
            "convergence, with data requirements growing very slowly as D ~ C^{0.27} with "
            "training compute.",
         "zh":
            "收敛是低效的。在固定的算力预算 C 下,若不对模型规模 N 或可用数据 D 施加其它约束, "
            "我们应当训练非常大的模型,并在远未收敛时就提前停止训练。因此,算力最优的训练比 "
            "基于训练小模型至收敛的预期要样本高效得多,数据需求随训练算力增长得非常缓慢, "
            "大致为 D ∝ C^{0.27}。"},

        {"type": "p", "en":
            "Optimal batch size. The ideal batch size for training these models is roughly a "
            "power of the loss only, and continues to be determinable by measuring the gradient "
            "noise scale; it is roughly 1–2 million tokens at convergence for the largest models "
            "we can train.",
         "zh":
            "最优批大小。这些模型训练的理想批大小大致仅由损失的某个幂次决定,并且仍然可以通 "
            "过梯度噪声规模来确定;在我们所能训练的最大模型上,收敛时的批大小约为 100–200 "
            "万个标记。"},

        {"type": "p", "en":
            "Taken together, these results show that language modeling performance improves "
            "smoothly and predictably as we appropriately scale up model size, data, and "
            "compute. We expect that larger language models will perform better and be more "
            "sample efficient than current models.",
         "zh":
            "综上,这些结果表明:只要我们适当增大模型规模、数据和算力,语言建模性能就会平滑 "
            "且可预测地提升。我们预期,更大的语言模型将比当前模型表现更好、且更样本高效。"},

        {"type": "h2", "text": "1.2 Summary of Scaling Laws | 尺度定律汇总"},

        {"type": "p", "en":
            "The test loss of a Transformer trained to autoregressively model language can be "
            "predicted using a power-law when performance is limited by only either the number "
            "of non-embedding parameters N, the dataset size D, or the optimally allocated "
            "compute budget C_min:",
         "zh":
            "当性能仅受到非嵌入参数量 N、数据集规模 D 或最优算力预算 C_min 其中之一的限制 "
            "时,可以用幂律来预测自回归语言 Transformer 的测试损失:"},

        {"type": "math", "en":
            "L(N)      = (N_c / N)^{α_N},     α_N ≈ 0.076,  N_c ≈ 8.8 × 10¹³ (non-embed params)<br/>"
            "L(D)      = (D_c / D)^{α_D},     α_D ≈ 0.095,  D_c ≈ 5.4 × 10¹³ tokens<br/>"
            "L(C_min)  = (C_c^min / C_min)^{α_C^min}, α_C^min ≈ 0.050, C_c^min ≈ 3.1 × 10⁸ PF-days",
         "zh":
            "L(N)     = (N_c / N)^{α_N},     α_N ≈ 0.076,  N_c ≈ 8.8 × 10¹³ (非嵌入参数量)<br/>"
            "L(D)     = (D_c / D)^{α_D},     α_D ≈ 0.095,  D_c ≈ 5.4 × 10¹³ tokens<br/>"
            "L(C_min) = (C_c^min / C_min)^{α_C^min}, α_C^min ≈ 0.050, C_c^min ≈ 3.1 × 10⁸ PF-days"},

        {"type": "p", "en":
            "These relations hold across eight orders of magnitude in C_min, six orders of "
            "magnitude in N, and over two orders of magnitude in D. They depend very weakly on "
            "model shape and other Transformer hyperparameters (depth, width, number of "
            "self-attention heads), with specific numerical values associated with the WebText2 "
            "training set. The power laws α_N, α_D, α_C^min specify the degree of performance "
            "improvement expected as we scale up N, D, or C_min; for example, doubling the "
            "number of parameters yields a loss that is smaller by a factor 2^{−α_N} ≈ 0.95. "
            "The precise numerical values of N_c, C_c^min, and D_c depend on the vocabulary size "
            "and tokenization and hence do not have a fundamental meaning.",
         "zh":
            "这些关系在 C_min 上跨越 8 个数量级、在 N 上跨越 6 个数量级、在 D 上跨越 2 个以 "
            "上的数量级。它们几乎与模型形状及其它 Transformer 超参数(深度、宽度、自注意力 "
            "头数)无关,具体数值与 WebText2 训练集相对应。幂律指数 α_N、α_D、α_C^min 刻画 "
            "了随 N、D、C_min 扩大而带来的性能提升程度;例如,参数量翻倍,损失减小 2^{−α_N} "
            "≈ 0.95 倍。N_c、C_c^min、D_c 的具体数值依赖于词表大小和分词方式,故并无根本性意 "
            "义。"},

        {"type": "p", "en":
            "The critical batch size, which determines the speed/efficiency tradeoff for data "
            "parallelism, also roughly obeys a power law in L: B_crit(L) = B_∗ / L^{1/α_B}, "
            "with B_∗ ≈ 2 × 10⁸ tokens and α_B ≈ 0.21.",
         "zh":
            "决定数据并行速度/效率权衡的临界批大小,也大致服从关于 L 的幂律:"
            "B_crit(L) = B_∗ / L^{1/α_B},其中 B_∗ ≈ 2 × 10⁸ tokens,α_B ≈ 0.21。"},

        {"type": "p", "en":
            "Equations (1) and (2) together suggest that as we increase the model size, we "
            "should increase the dataset size sublinearly according to D ∝ N^{α_N / α_D} ~ "
            "N^{0.74}. In fact, we find that there is a single equation combining (1) and (2) "
            "that governs the simultaneous dependence on N and D and governs the degree of "
            "overfitting:",
         "zh":
            "公式 (1) 与 (2) 共同表明:随着模型规模增大,我们应当按 D ∝ N^{α_N / α_D} ~ "
            "N^{0.74} 这种次线性关系增加数据。事实上,我们找到了一个同时刻画 N 与 D 依赖关系 "
            "并刻画过拟合程度的统一公式:"},

        {"type": "math", "en":
            "L(N, D) = [ (N_c / N)^{α_N / α_D} + D_c / D ]^{α_D}",
         "zh":
            "L(N, D) = [ (N_c / N)^{α_N / α_D} + D_c / D ]^{α_D}"},

        {"type": "p", "en":
            "with fits pictured on the left in Figure 2. We conjecture that this functional "
            "form may also parameterize the trained log-likelihood for other generative "
            "modeling tasks.",
         "zh":
            "其拟合结果如图 2 左侧所示。我们猜想,这一函数形式也可能刻画其它生成式建模任务中 "
            "训练得到的对数似然。"},

        {"type": "p", "en":
            "When training a given model for a finite number of parameter update steps S in the "
            "infinite data limit, after an initial transient period, the learning curves can be "
            "accurately fit by L(N, S) = (N_c / N)^{α_N} + (S_c / S_min(S))^{α_S}, where "
            "S_c ≈ 2.1 × 10³ and α_S ≈ 0.76, and S_min(S) is the minimum possible number of "
            "optimization steps estimated using the adjusted-steps formula.",
         "zh":
            "在无穷数据极限下,给定模型经有限步参数更新 S 训练时,经过初始的瞬态期后,学习 "
            "曲线可以被 L(N, S) = (N_c / N)^{α_N} + (S_c / S_min(S))^{α_S} 精确拟合,其中 "
            "S_c ≈ 2.1 × 10³,α_S ≈ 0.76,S_min(S) 是由调整后的步数公式估计出的最优化步数。"},

        {"type": "p", "en":
            "When training within a fixed compute budget C, but with no other constraints, the "
            "equation above leads to the prediction that the optimal model size N, optimal "
            "batch size B, optimal number of steps S, and dataset size D should grow as "
            "N ∝ C^{α_C^min / α_N}, B ∝ C^{α_C^min / α_B}, S ∝ C^{α_C^min / α_S}, D = B · S, "
            "with α_C^min = 1 / (1/α_S + 1/α_B + 1/α_N), which closely matches the empirically "
            "optimal results N ∝ C_min^{0.73}, B ∝ C_min^{0.24}, and S ∝ C_min^{0.03}. As the "
            "computational budget C increases, it should be spent primarily on larger models, "
            "without dramatic increases in training time or dataset size.",
         "zh":
            "在固定算力预算 C 下,若不施加其它约束,上述方程可预测最优模型规模 N、最优批大 "
            "小 B、最优步数 S 以及数据集规模 D 应满足: N ∝ C^{α_C^min / α_N},B ∝ "
            "C^{α_C^min / α_B},S ∝ C^{α_C^min / α_S},D = B · S,其中 α_C^min = 1 / (1/α_S + "
            "1/α_B + 1/α_N)。这与经验最优结果 N ∝ C_min^{0.73}、B ∝ C_min^{0.24}、S ∝ "
            "C_min^{0.03} 高度吻合。随着算力预算 C 的增加,应主要投入到更大的模型上,而训练时 "
            "间或数据集规模则不必大幅增加。"},

        {"type": "h2", "text": "1.3 Notation | 记号说明"},

        {"type": "p", "en":
            "We use the following notation:",
         "zh": "本文使用的记号如下:"},

        {"type": "p", "en":
            "• L — the cross entropy loss in nats. Typically averaged over the tokens in a "
            "context, but in some cases we report the loss for specific tokens within the "
            "context.<br/>"
            "• N — the number of model parameters, excluding all vocabulary and positional "
            "embeddings.<br/>"
            "• C ≈ 6 N B S — an estimate of the total non-embedding training compute, where B "
            "is the batch size, and S is the number of training steps (parameter updates). We "
            "quote numerical values in PF-days (1 PF-day = 8.64 × 10¹⁹ FLOPs).<br/>"
            "• D — the dataset size in tokens.<br/>"
            "• B_crit — the critical batch size, defined and discussed in Section 5.1. "
            "Training at B_crit provides a roughly optimal compromise between time and compute "
            "efficiency.<br/>"
            "• C_min — an estimate of the minimum amount of non-embedding compute to reach a "
            "given value of the loss.<br/>"
            "• S_min — an estimate of the minimal number of training steps needed to reach a "
            "given value of the loss.<br/>"
            "• α_X — power-law exponents for the scaling of the loss as L(X) ∝ 1 / X^{α_X} "
            "where X can be any of N, D, C, S, B, C_min.",
         "zh":
            "• L —— 交叉熵损失(以 nats 为单位)。通常取上下文内标记上的平均值;但在某些情 "
            "况下,会报告上下文中特定位置的损失。<br/>"
            "• N —— 模型参数数量,不包括所有词嵌入与位置嵌入。<br/>"
            "• C ≈ 6 N B S —— 非嵌入训练算力的估计值,其中 B 为批大小,S 为训练步数(即参数更 "
            "新次数)。我们以 PF-days 为单位给出数值(1 PF-day = 8.64 × 10¹⁹ 次浮点运算)。<br/>"
            "• D —— 数据集规模(以 token 为单位)。<br/>"
            "• B_crit —— 临界批大小,定义与讨论见第 5.1 节。在 B_crit 下训练大致能在时间与 "
            "算力效率之间取得最优折中。<br/>"
            "• C_min —— 达到给定损失值所需的最小非嵌入算力的估计。<br/>"
            "• S_min —— 达到给定损失值所需的最少训练步数的估计。<br/>"
            "• α_X —— 损失尺度关系的幂律指数,即 L(X) ∝ 1 / X^{α_X},其中 X 可以是 N、D、"
            "C、S、B、C_min 中的任意一个。"},

        {"type": "h1", "text": "2. Background and Methods | 背景与方法"},

        {"type": "p", "en":
            "We train language models on WebText2, an extended version of the WebText dataset, "
            "tokenized using byte-pair encoding with a vocabulary size n_vocab = 50257. We "
            "optimize the autoregressive log-likelihood (i.e. cross-entropy loss) averaged over "
            "a 1024-token context, which is also our principal performance metric. We record "
            "the loss on the WebText2 test distribution and on a selection of other text "
            "distributions. We primarily train decoder-only Transformer models, though we also "
            "train LSTM models and Universal Transformers for comparison.",
         "zh":
            "我们在 WebText2(扩展版 WebText 数据集)上训练语言模型,使用字节对编码 (BPE) 进 "
            "行分词,词表大小 n_vocab = 50257。我们优化 1024 token 上下文上的自回归对数似然 "
            "(即交叉熵损失),这也是我们主要的性能指标。我们在 WebText2 测试集分布以及若干其 "
            "它文本分布上记录损失。我们主要训练仅含解码器的 Transformer 模型,同时为对比也训 "
            "练了 LSTM 模型与 Universal Transformer。"},

        {"type": "h2", "text": "2.1 Parameter and Compute Scaling of Transformers | Transformer 的参数与算力尺度"},

        {"type": "p", "en":
            "We parameterize the Transformer architecture using hyperparameters n_layer (number "
            "of layers), d_model (dimension of the residual stream), d_ff (dimension of the "
            "intermediate feed-forward layer), d_attn (dimension of the attention output), and "
            "n_heads (number of attention heads per layer). We include n_ctx tokens in the "
            "input context, with n_ctx = 1024 except where otherwise noted.",
         "zh":
            "我们用以下超参数刻画 Transformer 架构:n_layer(层数)、d_model(残差流维度)、"
            "d_ff(中间前馈层维度)、d_attn(注意力输出维度)以及 n_heads(每层注意力头数)。 "
            "输入上下文包含 n_ctx 个 token,除特别说明外,n_ctx = 1024。"},

        {"type": "p", "en":
            "We use N to denote the model size, which we define as the number of non-embedding "
            "parameters: N ≈ 2 d_model n_layer (2 d_attn + d_ff) = 12 n_layer d_model² with the "
            "standard d_attn = d_ff / 4 = d_model, where we have excluded biases and other "
            "sub-leading terms. Our models also have n_vocab · d_model parameters in an "
            "embedding matrix, and use n_ctx · d_model parameters for positional embeddings, but "
            "we do not include these when discussing the model size N; we will see that this "
            "produces significantly cleaner scaling laws.",
         "zh":
            "我们用 N 表示模型规模,定义其为非嵌入参数量: N ≈ 2 d_model n_layer (2 d_attn + "
            "d_ff) = 12 n_layer d_model²(在标准设置 d_attn = d_ff / 4 = d_model 下),其中已 "
            "排除偏置及其它次要项。模型还有 n_vocab · d_model 个词嵌入矩阵参数,以及 n_ctx · "
            "d_model 个位置嵌入参数;但在讨论模型规模 N 时,我们不计入这些参数——之后我们会看 "
            "到,这样做能带来显著更干净的尺度定律。"},

        {"type": "p", "en":
            "Evaluating a forward pass of the Transformer involves roughly "
            "C_forward ≈ 2 N + 2 n_layer n_ctx d_model add-multiply operations, where the "
            "factor of two comes from the multiply-accumulate operation used in matrix "
            "multiplication. A more detailed per-operation parameter and compute count is "
            "included in Table 1. For contexts and models with d_model > n_ctx / 12, the "
            "context-dependent computational cost per token is a relatively small fraction of "
            "the total compute. Since we primarily study models where d_model >> n_ctx / 12, we "
            "do not include context-dependent terms in our training compute estimate. "
            "Accounting for the backwards pass (approximately twice the compute as the forwards "
            "pass), we then define the estimated non-embedding compute as C ≈ 6 N floating "
            "point operators per training token.",
         "zh":
            "评估 Transformer 的一次前向传播大约需要 C_forward ≈ 2 N + 2 n_layer n_ctx d_model "
            "次乘加运算(其中因子 2 来自矩阵乘法中的乘累加操作)。更详细的每操作参数与算力 "
            "计数见表 1。对于 d_model > n_ctx / 12 的上下文与模型,与上下文相关的每 token 计算 "
            "成本在总算力中只占很小一部分。由于我们主要研究 d_model 远大于 n_ctx / 12 的模 "
            "型,因此在训练算力的估计中不计与上下文相关的项。考虑反向传播(算力约为前向传播的 "
            "两倍),我们将估计的非嵌入算力定义为每训练 token 约 C ≈ 6 N 次浮点运算。"},

        {"type": "table",
         "col_widths": [3.5 * cm, 5.0 * cm, 5.0 * cm],
         "rows": [
             ["Operation / 操作", "Parameters / 参数量", "FLOPs per Token / 每 token FLOPs"],
             ["Embed", "(n_vocab + n_ctx) · d_model", "4 d_model"],
             ["Attention: QKV", "n_layer · d_model · 3 d_attn", "2 n_layer · d_model · 3 d_attn"],
             ["Attention: Mask", "—", "2 n_layer · n_ctx · d_attn"],
             ["Attention: Project", "n_layer · d_attn · d_model", "2 n_layer · d_attn · d_model"],
             ["Feedforward", "n_layer · 2 d_model · d_ff", "2 n_layer · 2 d_model · d_ff"],
             ["De-embed", "—", "2 d_model · n_vocab"],
             ["Total (Non-Embedding)", "N = 2 d_model n_layer (2 d_attn + d_ff)",
              "C_fwd = 2 N + 2 n_layer n_ctx d_attn"],
         ],
         "caption_en":
             "Table 1 — Parameter counts and compute (forward pass) estimates for a Transformer "
             "model. Sub-leading terms such as nonlinearities, biases, and layer normalization "
             "are omitted.",
         "caption_zh":
             "表 1 —— Transformer 模型的参数量与算力(前向传播)估计。表中略去了非线性、偏置、"
             "层归一化等次要项。"},

        {"type": "h2", "text": "2.2 Training Procedures | 训练流程"},

        {"type": "p", "en":
            "Unless otherwise noted, we train models with the Adam optimizer for a fixed "
            "2.5 × 10⁵ steps with a batch size of 512 sequences of 1024 tokens. Due to memory "
            "constraints, our largest models (more than 1B parameters) were trained with "
            "Adafactor. We experimented with a variety of learning rates and schedules, as "
            "discussed in the Appendix. We found that results at convergence were largely "
            "independent of learning rate schedule. Unless otherwise noted, all training runs "
            "included in our data used a learning rate schedule with a 3000 step linear warmup "
            "followed by a cosine decay to zero.",
         "zh":
            "除非另有说明,我们使用 Adam 优化器进行固定 2.5 × 10⁵ 步的训练,批大小为 512 个 "
            "长度为 1024 token 的序列。受显存限制,我们最大的模型(超过 10 亿参数)使用 "
            "Adafactor 训练。我们尝试了多种学习率与学习率调度(详见附录)。我们发现,收敛结 "
            "果几乎与学习率调度无关。除非另有说明,数据中包含的所有训练运行均使用 3000 步 "
            "线性 warmup 之后接余弦衰减至零的学习率调度。"},

        {"type": "h2", "text": "2.3 Datasets | 数据集"},

        {"type": "p", "en":
            "We train our models on an extended version of the WebText dataset. The original "
            "WebText dataset was a web scrape of outbound links from Reddit through December "
            "2017 which received at least 3 karma. In WebText2, we added outbound Reddit links "
            "from January to October 2018, also with a minimum of 3 karma. The karma threshold "
            "served as a heuristic for whether people found the link interesting or useful. The "
            "text of the new links was extracted with the Newspaper3k python library. In total, "
            "the dataset consists of 20.3M documents containing 96 GB of text and 1.62 × 10¹⁰ "
            "words. We then apply the reversible tokenizer, which yields 2.29 × 10¹⁰ tokens. "
            "We reserve 6.6 × 10⁸ of these tokens for use as a test set, and we also test on "
            "similarly-prepared samples of Books Corpus, Common Crawl, English Wikipedia, and a "
            "collection of publicly-available Internet Books.",
         "zh":
            "我们在 WebText 数据集的扩展版上训练模型。原始 WebText 是从 Reddit 中抽取的外链 "
            "网页抓取,截至 2017 年 12 月,要求每条链接至少获得 3 个 karma。在 WebText2 中, "
            "我们新增了 2018 年 1 月至 10 月的 Reddit 外链,同样要求至少 3 个 karma。karma 阈 "
            "值作为一条启发式规则,用以判断链接是否对人们有趣或有用。新增链接的文本通过 "
            "Newspaper3k 这个 Python 库抽取。整体而言,数据集共包含 2030 万篇文档、96 GB 文 "
            "本、1.62 × 10¹⁰ 个词。然后我们应用可逆的分词器,得到 2.29 × 10¹⁰ 个 token。 "
            "我们将其中 6.6 × 10⁸ 个 token 留作测试集,同时还在 Books Corpus、Common Crawl、"
            "英文维基百科以及一组公开可用的 Internet Books 的同种处理样本上进行测试。"},

        {"type": "h1", "text": "3. Empirical Results and Basic Power Laws | 实验结果与基本幂律"},

        {"type": "p", "en":
            "To characterize language model scaling we train a wide variety of models, varying "
            "a number of factors including: model size (ranging in size from 768 to 1.5 billion "
            "non-embedding parameters); dataset size (ranging from 22 million to 23 billion "
            "tokens); shape (including depth, width, attention heads, and feed-forward "
            "dimension); context length (1024 for most runs, though we also experiment with "
            "shorter contexts); and batch size (2¹⁹ for most runs, but we also vary it to "
            "measure the critical batch size).",
         "zh":
            "为刻画语言模型的尺度,我们在多种因素上变化训练:模型规模(从 768 到 15 亿非嵌 "
            "入参数);数据集规模(从 2 200 万到 230 亿 token);形状(深度、宽度、注意力头、"
            "前馈维度);上下文长度(大多数运行使用 1024,同时也实验了更短的上下文);批大 "
            "小(大多数运行使用 2¹⁹,但我们也改变它以测量临界批大小)。"},

        {"type": "p", "en":
            "In this section we will display data along with empirically-motivated fits, "
            "deferring theoretical analysis to later sections.",
         "zh":
            "本节我们将展示数据及由经验驱动的拟合,而将理论分析留到后续章节。"},

        {"type": "h2", "text": "3.1 Approximate Transformer Shape and Hyperparameter Independence | "
                              "Transformer 形状与超参数近似无关性"},

        {"type": "p", "en":
            "Transformer performance depends very weakly on the shape parameters n_layer, "
            "n_heads, and d_ff when we hold the total non-embedding parameter count N fixed. "
            "To establish these results we trained models with fixed size while varying a "
            "single hyperparameter. This was simplest for the case of n_heads. When varying "
            "n_layer, we simultaneously varied d_model while keeping N ≈ 12 n_layer d_model² "
            "fixed. Similarly, to vary d_ff at fixed model size we also simultaneously varied "
            "the d_model parameter, as required by the parameter counts in Table 1. "
            "Independence of n_layers would follow if deeper Transformers effectively behave as "
            "ensembles of shallower models, as has been suggested for ResNets.",
         "zh":
            "在保持总非嵌入参数量 N 不变的情况下,Transformer 的性能几乎不依赖于形状超参数 "
            "n_layer、n_heads 和 d_ff。为建立这一结论,我们在固定规模的同时,逐个改变某一 "
            "个超参数进行了实验。最直接的是 n_heads。改变 n_layer 时,我们同时调整 d_model "
            "以保持 N ≈ 12 n_layer d_model² 不变。类似地,在固定 N 下改变 d_ff 时,我们也同 "
            "时改变 d_model(如表 1 中的参数量公式所要求的)。如果更深的 Transformer 实际上 "
            "表现为若干浅层模型的集成(有人曾对 ResNet 提出过类似观点),那么 n_layer 的无关 "
            "性也就顺理成章了。"},

        {"type": "h2", "text": "3.2 Performance with Non-Embedding Parameter Count N | "
                              "性能与非嵌入参数量 N 的关系"},

        {"type": "p", "en":
            "We display the performance of a wide variety of models, ranging from small models "
            "with shape (n_layer, d_model) = (2, 128) through billion-parameter models, "
            "ranging in shape from (6, 4288) through (207, 768). Here we have trained to near "
            "convergence on the full WebText2 dataset and observe no overfitting (except "
            "possibly for the very largest models).",
         "zh":
            "我们展示了大量模型的性能——从形状 (n_layer, d_model) = (2, 128) 的小模型,到形 "
            "状从 (6, 4288) 到 (207, 768) 的十亿参数模型。我们是在完整的 WebText2 数据集上 "
            "训练至接近收敛的,且没有观察到过拟合(最大的几个模型可能除外)。"},

        {"type": "p", "en":
            "We find a steady trend with non-embedding parameter count N, which can be fit to "
            "the first term of the L(N, D) equation, so that L(N) ≈ (N_c / N)^{α_N}. To "
            "observe these trends it is crucial to study performance as a function of N; if we "
            "instead use the total parameter count (including the embedding parameters) the "
            "trend is somewhat obscured. This suggests that the embedding matrix can be made "
            "smaller without impacting performance, as has been seen in recent work.",
         "zh":
            "我们发现非嵌入参数量 N 与性能呈现稳定的趋势,可以由 L(N, D) 公式的第一项拟合, "
            "即 L(N) ≈ (N_c / N)^{α_N}。要观察这一趋势,必须以 N 为自变量来研究性能;若使用 "
            "总参数量(含嵌入参数),趋势会变得模糊。这说明词嵌入矩阵可以做得更小而不影响性 "
            "能——近期工作中也观察到了这一点。"},

        {"type": "p", "en":
            "Although these models have been trained on the WebText2 dataset, their test loss "
            "on a variety of other datasets is also a power-law in N with nearly identical "
            "power, as shown in Figure on generalization vs model size.",
         "zh":
            "尽管这些模型只在 WebText2 上训练,但它们在多种其它数据集上的测试损失同样与 N "
            "呈幂律关系,且幂律指数几乎相同(参见泛化与模型规模图)。"},

        {"type": "h2", "text": "3.3 Performance with Dataset Size and Compute | "
                              "性能与数据集规模、算力的关系"},

        {"type": "p", "en":
            "We display empirical trends for the test loss as a function of dataset size D (in "
            "tokens) and training compute C in Figure on basic power laws. For the trend with D "
            "we trained a model with (n_layer, n_embd) = (36, 1280) on fixed subsets of the "
            "WebText2 dataset. We stopped training once the test loss ceased to decrease. We "
            "see that the resulting test losses can be fit with simple power-law "
            "L(D) ≈ (D_c / D)^{α_D} in the dataset size.",
         "zh":
            "我们在基本幂律图中展示了测试损失作为数据集规模 D(以 token 计)和训练算力 C "
            "的函数所呈现的经验趋势。在与 D 的关系上,我们在 WebText2 的固定子集上训练了一 "
            "个形状为 (n_layer, n_embd) = (36, 1280) 的模型,并在测试损失不再下降时停止训 "
            "练。我们发现,所得的测试损失可由 L(D) ≈ (D_c / D)^{α_D} 这一简单的幂律拟合。"},

        {"type": "p", "en":
            "The total amount of non-embedding compute used during training can be estimated "
            "as C = 6 N B S, where B is the batch size, S is the number of parameter updates, "
            "and the factor of 6 accounts for the forward and backward passes. Thus for a given "
            "value of C we can scan over all models with various N to find the model with the "
            "best performance on step S = C / (6 B S). Note that in these results the batch "
            "size B remains fixed for all models, which means that these empirical results are "
            "not truly optimal. We will account for this in later sections using an adjusted "
            "C_min to produce cleaner trends. The result can be fit with L(C) ≈ (C_c / C)^{α_C}. "
            "The data strongly suggests that sample efficiency improves with model size.",
         "zh":
            "训练过程中使用的总非嵌入算力可估计为 C = 6 N B S,其中 B 为批大小,S 为参数更 "
            "新次数,因子 6 涵盖了前向与反向传播。因此,对于给定的 C,我们可以在不同 N 的模 "
            "型上扫描,找到在 S = C / (6 B S) 步上性能最佳的模型。需要注意的是,在这些结果 "
            "中,所有模型使用的批大小 B 都是固定的,这意味着这些经验结果并非真正最优。我们 "
            "将在后续章节中通过调整后的 C_min 来解释这一点,从而得到更干净的趋势。结果可由 "
            "L(C) ≈ (C_c / C)^{α_C} 拟合。数据强烈表明:样本效率随模型规模的增大而提升。"},

        {"type": "h1", "text": "4. Charting the Infinite Data Limit and Overfitting | "
                              "刻画无穷数据极限与过拟合"},

        {"type": "p", "en":
            "In Section 3 we found a number of basic scaling laws for language modeling "
            "performance. Here we will study the performance of a model of size N trained on a "
            "dataset with D tokens while varying N and D simultaneously. We will empirically "
            "demonstrate that the optimally trained test loss accords with the scaling law "
            "L(N, D). This provides guidance on how much data we would need to train models of "
            "increasing size while keeping overfitting under control.",
         "zh":
            "在第 3 节中,我们发现了若干基本的语言建模性能尺度定律。本节中,我们将研究在 "
            "同时变化 N 与 D 时,一个规模为 N、在 D 个 token 数据集上训练的模型的性能。我们 "
            "将以经验方式证明:经过最优训练的测试损失服从 L(N, D) 这一尺度定律。这为我们在 "
            "控制过拟合的前提下训练不断增大的模型所需的数据量提供了指引。"},

        {"type": "h2", "text": "4.1 Proposed L(N, D) Equation | 提出的 L(N, D) 公式"},

        {"type": "p", "en":
            "We have chosen the parameterization L(N, D) = [(N_c / N)^{α_N / α_D} + D_c / D]^{α_D} "
            "using three principles:",
         "zh":
            "我们采用 L(N, D) = [(N_c / N)^{α_N / α_D} + D_c / D]^{α_D} 这一参数形式,基于 "
            "三条原则:"},

        {"type": "p", "en":
            "• Changes in vocabulary size or tokenization are expected to rescale the loss by "
            "an overall factor. The parameterization of L(N, D) (and all models of the loss) "
            "must naturally allow for such a rescaling.<br/>"
            "• Fixing D and sending N → ∞, the overall loss should approach L(D). Conversely, "
            "fixing N and sending D → ∞ the loss must approach L(N).<br/>"
            "• L(N, D) should be analytic at D = ∞, so that it has a series expansion in 1/D "
            "with integer powers. Theoretical support for this principle is significantly "
            "weaker than for the first two.",
         "zh":
            "• 词表大小或分词方式的变化预期只会对损失乘以一个整体常数。因此,L(N, D)(以及 "
            "所有刻画损失的模型)的参数形式必须自然地允许这种整体缩放。<br/>"
            "• 固定 D 并令 N → ∞,整体损失应趋于 L(D)。反过来,固定 N 并令 D → ∞,损失必须 "
            "趋于 L(N)。<br/>"
            "• L(N, D) 应当在 D = ∞ 处解析,从而在 1/D 上可做整数次幂的级数展开。这一原则的 "
            "理论支持显著弱于前两条。"},

        {"type": "p", "en":
            "Our choice of L(N, D) satisfies the first requirement because we can rescale N_c, "
            "D_c with changes in the vocabulary. This also implies that the values of N_c, D_c "
            "have no fundamental meaning. Since we stop training early when the test loss "
            "ceases to improve and optimize all models in the same way, we expect that larger "
            "models should always perform better than smaller models. But with fixed finite D, "
            "we also do not expect any model to be capable of approaching the best possible loss "
            "(i.e. the entropy of text). Similarly, a model with fixed size will be "
            "capacity-limited. These considerations motivate our second principle. Knowledge of "
            "L(N) at infinite D and L(D) at infinite N fully determines all the parameters in "
            "L(N, D). The third principle explains the asymmetry between the roles of N and D "
            "in the equation. Very similar symmetric expressions are possible, but they would "
            "not have a 1/D expansion with integer powers, and would require the introduction "
            "of an additional parameter. In any case, we will see that our equation for "
            "L(N, D) fits the data well, which is the most important justification for our "
            "ansatz.",
         "zh":
            "我们选择的 L(N, D) 满足第一条要求,因为我们可以通过词表变化对 N_c、D_c 进行缩 "
            "放。这也意味着 N_c、D_c 的具体数值并无根本意义。由于我们在测试损失不再下降时 "
            "提前停止训练,并以相同方式优化所有模型,我们预期更大的模型总是优于更小的模型; "
            "但在固定有限 D 下,我们不预期任何模型能达到可能的最佳损失(即文本的熵)。类似地, "
            "固定规模的模型存在容量上限。这些考量是第二条原则的依据。在无穷 D 处的 L(N) 与 "
            "在无穷 N 处的 L(D) 完全确定了 L(N, D) 中的所有参数。第三条原则解释了公式中 N 与 "
            "D 之间的不对称性。类似的、形式上更对称的表达式是存在的,但它们在 1/D 上没有整 "
            "数次幂的展开,且需要引入额外的参数。无论如何,我们将看到,L(N, D) 公式能很好 "
            "地拟合数据,这是我们采用这一拟设的最重要依据。"},

        {"type": "h2", "text": "4.2 Results | 实验结果"},

        {"type": "p", "en":
            "We regularize all our models with 10% dropout, and by tracking test loss and "
            "stopping once it is no longer decreasing. The results are displayed in Figure 3, "
            "including a fit to the four parameters α_N, α_D, N_c, D_c in L(N, D): α_N = "
            "0.076, α_D = 0.103, N_c = 6.4 × 10¹³, D_c = 1.8 × 10¹³.",
         "zh":
            "我们对所有模型使用 10% 的 dropout,并通过追踪测试损失、待其不再下降时停止训 "
            "练。拟合 L(N, D) 中四个参数 α_N、α_D、N_c、D_c 的结果如图 3 所示:α_N = "
            "0.076,α_D = 0.103,N_c = 6.4 × 10¹³,D_c = 1.8 × 10¹³。"},

        {"type": "p", "en":
            "We obtain an excellent fit, with the exception of the runs where the dataset has "
            "been reduced by a factor of 1024, to about 2 × 10⁷ tokens. With such a small "
            "dataset, an epoch consists of only 40 parameter updates. Perhaps such a tiny "
            "dataset represents a different regime for language modeling, as overfitting "
            "happens very early in training.",
         "zh":
            "除了将数据集缩减为原来的 1/1024(约 2 × 10⁷ token)的那些运行外,我们都得到了优 "
            "秀的拟合。这么小的数据集,一个 epoch 仅包含 40 次参数更新。或许这种极小的数据集 "
            "代表语言建模的一种不同模式,因为过拟合在训练初期就会发生。"},

        {"type": "p", "en":
            "To chart the borderlands of the infinite data limit, we can directly study the "
            "extent of overfitting. For all but the largest models, we see no sign of "
            "overfitting when training with the full 22B token WebText2 dataset, so we can take "
            "it as representative of D = ∞. Thus we can compare finite D to the infinite data "
            "limit by defining δL(N, D) ≡ L(N, D) / L(N, ∞) − 1 and studying it as a function "
            "of N, D. We see empirically that δL depends only a specific combination of N and "
            "D, as shown in the appendix.",
         "zh":
            "为了刻画无穷数据极限的边界,我们可以直接研究过拟合的程度。除最大的模型之外, "
            "在完整 220 亿 token 的 WebText2 数据集上训练时,我们看不到任何过拟合迹象,因此可 "
            "以把它视为 D = ∞ 的代表。我们可以定义 δL(N, D) ≡ L(N, D) / L(N, ∞) − 1,以此 "
            "来比较有限 D 与无穷数据极限。经验上我们发现,δL 只依赖于 N 与 D 的某个特定组合 "
            "(详见附录)。"},

        {"type": "p", "en":
            "We estimate that the variation in the loss with different random seeds is roughly "
            "0.02, which means that to avoid overfitting when training to within that threshold "
            "of convergence we require D ≳ (5 × 10³) · N^{0.74}. With this relation, models "
            "smaller than 10⁹ parameters can be trained with minimal overfitting on the 22B "
            "token WebText2 dataset, but our largest models will encounter some mild "
            "overfitting. More generally, this relation shows that dataset size may grow "
            "sub-linearly in model size while avoiding overfitting. Note however that this does "
            "not typically represent maximally compute-efficient training. We should also "
            "emphasize that we have not optimized regularization (e.g. the dropout probability) "
            "while varying dataset and model size.",
         "zh":
            "我们估计,在不同随机种子下损失的变化约为 0.02,因此为了在训练至与收敛相差此阈 "
            "值时避免过拟合,我们需要 D ≳ (5 × 10³) · N^{0.74}。按此关系,在 220 亿 token 的 "
            "WebText2 上训练 10⁹ 参数以下的模型几乎不会出现过拟合,但我们的最大模型会遭遇一 "
            "定程度的轻微过拟合。更一般地,这一关系表明:为避免过拟合,数据集规模可以按模型 "
            "规模的次线性增长。不过,这种关系通常并不代表算力最优的训练方式。我们还须强调, "
            "在变化数据集与模型规模时,我们并未优化正则化(如 dropout 概率)。"},

        {"type": "h1", "text": "5. Scaling Laws with Model Size and Training Time | "
                              "模型规模与训练时间的尺度定律"},

        {"type": "p", "en":
            "In this section we will demonstrate that a simple scaling law provides a good "
            "description for the loss as a function of model size N and training time. First "
            "we will explain how to use previous results to define a universal training step "
            "S_min, which accounts for the fact that most of our models have not been trained "
            "at an optimal batch size. Then we will demonstrate that we can fit the model size "
            "and training time dependence of the loss using L(N, S). Later we will use these "
            "results to predict the optimal allocation of training compute between model size "
            "and training time, and then confirm that prediction.",
         "zh":
            "本节中,我们将证明:一个简单的尺度定律能够很好地刻画损失作为模型规模 N 与训练 "
            "时间的函数。首先,我们将说明如何利用已有结果定义一个普适的训练步数 S_min,以 "
            "解释大多数模型并未在最优批大小下训练这一事实。然后,我们将证明可以用 L(N, S) "
            "来拟合损失对模型规模与训练时间的依赖。后续我们将利用这些结果预测模型规模与训 "
            "练时间之间的最优算力分配,并通过实验加以验证。"},

        {"type": "h2", "text": "5.1 Adjustment for Training at B_crit(L) | 按 B_crit(L) 调整训练"},

        {"type": "p", "en":
            "A simple empirical theory for the batch size dependence of training was developed "
            "in prior work. It was argued that there is a critical batch size B_crit for "
            "training; for B up to B_crit the batch size can be increased with very minimal "
            "degradation in compute-efficiency, whereas for B > B_crit increases in B result "
            "in diminishing returns. It was also argued that the gradient noise scale provides "
            "a simple prediction for B_crit, and that neither depends directly on model size "
            "except through the value of the loss that has been attained. These results can be "
            "used to predict how training time and compute will vary with the batch size. To "
            "utilize both training time and compute as effectively as possible, it is best to "
            "train with a batch size B ≈ B_crit.",
         "zh":
            "前人工作发展了一套关于训练中批大小依赖的简单经验理论。该理论认为训练存在一个 "
            "临界批大小 B_crit:在 B ≤ B_crit 的范围内,增大批大小对算力效率的影响极小;而当 "
            "B > B_crit 时,继续增大 B 会出现收益递减。该理论还指出,梯度噪声规模为 B_crit 提 "
            "供了一种简单的预测,且两者都只通过损失值间接依赖于模型规模,而不直接依赖于 N。 "
            "这些结果可以预测训练时间与算力随批大小的变化。要同时最有效地利用时间与算力,最 "
            "好在 B ≈ B_crit 下进行训练。"},

        {"type": "p", "en":
            "More specifically, it was demonstrated that for a wide variety of neural network "
            "tasks, the number of training steps S and the number of data examples processed "
            "E = B S satisfy the simple relation (S / S_min − 1)(E / E_min − 1) = 1 when "
            "training to any fixed value of the loss L. Here S_min is the minimum number of "
            "steps necessary to reach L, while E_min is the minimum number of data examples "
            "that must be processed. This relation defines the critical batch size B_crit(L) "
            "≡ E_min / S_min, which is a function of the target value of the loss. Training at "
            "the critical batch size makes a roughly optimal time/compute tradeoff, requiring "
            "2 S_min training steps and processing E = 2 E_min data examples.",
         "zh":
            "更具体地说,前人证明:对于多种神经网络任务,在训练至任意固定的损失值 L 时,训 "
            "练步数 S 与处理的数据样本数 E = B S 满足简单关系 (S / S_min − 1)(E / E_min − "
            "1) = 1。其中 S_min 是达到 L 所需的最少步数,E_min 是必须处理的最少样本数。 "
            "该关系定义了临界批大小 B_crit(L) ≡ E_min / S_min,它只是目标损失值的函数。在临 "
            "界批大小下训练大致能给出一个最优的时间/算力折中:需要 2 S_min 步训练,处理 E = "
            "2 E_min 个样本。"},

        {"type": "p", "en":
            "In our experiments we plotted the critical batch size and gradient noise scale as "
            "a function of training loss for two different models. We see that B_crit(L) is "
            "independent of model size, and only depends on the loss L. So the predictions "
            "continue to hold for Transformer language models. The critical batch size can be "
            "fit with a power-law in the loss B_crit(L) ≈ B_∗ / L^{1/α_B}, where B_∗ ≈ 2 × 10⁸ "
            "and α_B ≈ 0.21. We have chosen this parameterization for B_crit(L) because as the "
            "loss approaches its minimum value L_min, the gradient noise scale is expected to "
            "diverge, and we expect B_crit to track this noise scale.",
         "zh":
            "在我们的实验中,我们针对两个不同的模型,绘制了临界批大小与梯度噪声规模随训练损 "
            "失的变化曲线。我们发现,B_crit(L) 与模型规模无关,只依赖于损失 L。因此,这些 "
            "预测同样适用于 Transformer 语言模型。临界批大小可由关于损失的幂律拟合:"
            "B_crit(L) ≈ B_∗ / L^{1/α_B},其中 B_∗ ≈ 2 × 10⁸,α_B ≈ 0.21。我们之所以选择 "
            "这种参数形式,是因为当损失接近其最小值 L_min 时,梯度噪声规模预期会发散,我们 "
            "预期 B_crit 会跟踪这一噪声规模。"},

        {"type": "p", "en":
            "We will use B_crit(L) to estimate the relation between the number of training "
            "steps S while training at batch size B = 2¹⁹ tokens and the number of training "
            "steps while training at B >> B_crit. This is simply S_min(S) ≡ S / (1 + B_crit(L) / B) "
            "(minimum steps, at B >> B_crit) for any given target value L for the loss. This "
            "also defines a critical value of the compute needed to train to L with a model of "
            "size N if we were to train at B << B_crit(L): C_min(C) ≡ C / (1 + B / B_crit(L)) "
            "(minimum compute, at B << B_crit), where C = 6 N B S estimates the (non-embedding) "
            "compute used at batch size B.",
         "zh":
            "我们将利用 B_crit(L) 来估计在批大小 B = 2¹⁹ tokens 下训练所需的步数 S 与在 "
            "B >> B_crit 下训练所需步数之间的关系。对任意目标损失 L,这简化为:"
            "S_min(S) ≡ S / (1 + B_crit(L) / B)(在 B >> B_crit 下的最少步数)。这也定义了在 "
            "B << B_crit(L) 下训练规模为 N 的模型至损失 L 所需的算力临界值:"
            "C_min(C) ≡ C / (1 + B / B_crit(L))(在 B << B_crit 下的最少算力),其中 C = 6 N B S "
            "是在批大小 B 下使用的(非嵌入)算力的估计。"},

        {"type": "h2", "text": "5.2 Results for L(N, S_min) | L(N, S_min) 的结果"},

        {"type": "p", "en":
            "Now we will use S_min defined above to obtain a simple and universal fit for the "
            "dependence of the loss on model size and training time in the infinite data "
            "limit. We will fit the stable, Adam-optimized training runs using "
            "L(N, S_min) = (N_c / N)^{α_N} + (S_c / S_min)^{α_S} for the loss. We include all "
            "training steps after the warmup period of the learning rate schedule, and find a "
            "fit to the data with the parameters: α_N = 0.077, α_S = 0.76, N_c = 6.5 × 10¹³, "
            "S_c = 2.1 × 10³.",
         "zh":
            "现在我们将使用上文定义的 S_min,在无穷数据极限下得到一个简单而普适的、刻画损 "
            "失对模型规模与训练时间依赖的拟合。我们用 "
            "L(N, S_min) = (N_c / N)^{α_N} + (S_c / S_min)^{α_S} 对稳定的、由 Adam 优化的训 "
            "练运行进行拟合。我们只纳入学习率调度 warmup 之后的所有训练步,并得到参数拟合 "
            "结果:α_N = 0.077,α_S ≈ 0.76,N_c = 6.5 × 10¹³,S_c = 2.1 × 10³。"},

        {"type": "p", "en":
            "With these parameters, we obtain the learning curve fits. Though the fits are "
            "imperfect, we believe they are quite compelling given the simplicity of the "
            "equation. The power-law dependence of the loss on S_min reflects the interplay of "
            "optimizer dynamics and the loss landscape. Since the fits are best late in "
            "training, when the loss may be approximately quadratic, the power-law should "
            "provide information about the spectrum of the Hessian of the loss. Its "
            "universality suggests that the Hessian eigenvalue density is roughly independent "
            "of model size.",
         "zh":
            "在这些参数下,我们得到了学习曲线的拟合结果。尽管拟合并非完美,但考虑到该方程 "
            "的简洁性,我们认为拟合结果相当有说服力。损失对 S_min 的幂律依赖反映了优化器 "
            "动力学与损失景观之间的相互作用。由于拟合在训练后期(此时损失近似二次时)效果 "
            "最好,这一幂律应当能提供关于损失 Hessian 谱的信息。其普适性表明 Hessian 特征 "
            "值密度大致与模型规模无关。"},

        {"type": "h1", "text": "6. Optimal Allocation of the Compute Budget | "
                              "算力预算的最优分配"},

        {"type": "p", "en":
            "We displayed the empirical trend of performance as a function of the computation "
            "used during training in Figure 1. However, this result involved training at a "
            "fixed batch size B, whereas we know that in fact we could train more efficiently "
            "by training at the batch size B_crit discussed above. Large and small values of "
            "the loss could have been achieved with fewer samples or fewer steps, respectively, "
            "and correcting for this inefficiency by standardizing to the critical batch size "
            "results in cleaner and more predictable trends.",
         "zh":
            "我们曾在图 1 中展示性能作为训练所用算力的函数的经验趋势。然而,这一结果是在固 "
            "定批大小 B 下训练得到的,而事实上我们可以通过采用上文讨论的 B_crit 来更高效地训 "
            "练。更大的损失值本来可以用更少的样本来达到,更小的损失值本来可以用更少的步数来 "
            "达到;通过标准化到临界批大小来修正这种低效,可以得到更干净、更可预测的趋势。"},

        {"type": "p", "en":
            "In this section we will adjust for this oversight. More importantly, we will use "
            "the results of Section 5 to determine the optimal allocation of compute between "
            "model size N and the quantity of data processed during training, namely 2 B_crit "
            "S_min. We will determine this allocation both empirically and theoretically, by "
            "using the equation for L(N, S_min), and we will demonstrate that these methods "
            "agree.",
         "zh":
            "本节中我们将修正这一疏漏。更重要的是,我们将利用第 5 节的结果,确定模型规模 N "
            "与训练期间所处理的数据量(即 2 B_crit S_min)之间的算力最优分配。我们既会从经验 "
            "上,也会从理论上(借助 L(N, S_min) 方程)确定这一分配,并证明两种方法是吻合的。"},

        {"type": "h2", "text": "6.1 Optimal Performance and Allocations | 最优性能与分配"},

        {"type": "p", "en":
            "Let us first study the loss as a function of the optimally allocated compute from "
            "the adjusted compute formula. We see that as compared to the compute plot of "
            "Figure 1, the new fit with C_min is somewhat improved.",
         "zh":
            "首先,我们研究损失作为由调整后算力公式得到的最优分配算力的函数。我们发现,与 "
            "图 1 中的算力曲线相比,使用 C_min 的新拟合略有改善。"},

        {"type": "p", "en":
            "Given L(C_min), it is natural to ask for the optimal model size N(C_min) that "
            "provides the minimal loss with a given quantity of training compute. The optimal "
            "model size can be fit very well with a power-law N(C_min) ∝ C_min^{0.73}. We show "
            "the effect of training models of sub-optimal sizes in the appendix.",
         "zh":
            "有了 L(C_min),很自然地会问:在给定训练算力下,能达到最小损失的最优模型规模 "
            "N(C_min) 是多少?最优模型规模可由幂律 N(C_min) ∝ C_min^{0.73} 非常好地拟合。 "
            "训练次优尺寸模型的效果见附录。"},

        {"type": "p", "en":
            "By definition C_min ≡ 6 N B_crit S, and so we can use N(C_min) to extract further "
            "results. In particular, since prior fits show B ∝ L^{−4.8} and L ∝ C_min^{−0.05}, "
            "we can conclude that B_crit ∝ C_min^{0.24}. This leads us to conclude that the "
            "optimal number of steps will only grow very slowly with compute, as "
            "S_min ∝ C_min^{0.03}, matching the empirical results. In fact the measured "
            "exponent is sufficiently small that our results may even be consistent with an "
            "exponent of zero.",
         "zh":
            "根据定义 C_min ≡ 6 N B_crit S,因此我们可以利用 N(C_min) 推导出进一步的结果。 "
            "特别地,鉴于前文的拟合给出 B ∝ L^{−4.8} 和 L ∝ C_min^{−0.05},我们可以得到 "
            "B_crit ∝ C_min^{0.24}。由此得出最优步数只会随算力增长得非常缓慢:S_min ∝ "
            "C_min^{0.03},这与经验结果吻合。事实上,测得的指数已经小到可能与零指数一致。"},

        {"type": "p", "en":
            "Thus we conclude that as we scale up language modeling with an optimal allocation "
            "of computation, we should predominantly increase the model size N, while "
            "simultaneously scaling up the batch size via B ∝ B_crit with negligible increase "
            "in the number of serial steps. Since compute-efficient training uses relatively "
            "few optimization steps, additional work on speeding up early training dynamics may "
            "be warranted.",
         "zh":
            "因此我们得出结论:在以算力最优分配方式扩展语言建模时,我们应主要增大模型规模 "
            "N,同时通过 B ∝ B_crit 增大批大小,而串行步数几乎不必增加。由于算力高效的训 "
            "练使用的优化步数相对较少,进一步研究如何加速训练早期动力学可能是值得的。"},

        {"type": "h2", "text": "6.2 Predictions from L(N, S_min) | 由 L(N, S_min) 给出的预测"},

        {"type": "p", "en":
            "The results for L(C_min) and the allocations can be predicted from the L(N, S_min) "
            "equation obtained in Section 5. Given our equation for L(N, S_min), we can "
            "substitute S_min = C_min / (6 N B) and then find the minimum of the loss as a "
            "function of N, while fixing the training compute. For the loss as a function of "
            "training compute, we predict that L(C_min) = (C_c^min / C_min)^{α_C^min}, where "
            "α_C^min ≡ 1 / (1/α_S + 1/α_B + 1/α_N) ≈ 0.054, in excellent agreement with the "
            "exponent of Figure 4. We also predict that N(C_min) ∝ C_min^{α_C^min / α_N} ≈ "
            "C_min^{0.71}, which also matches the scaling of Figure on optimal model size to "
            "within a few percent. Our scaling laws provide a predictive framework for the "
            "performance of language modeling.",
         "zh":
            "L(C_min) 及其分配的结果可由第 5 节得到的 L(N, S_min) 方程预测。给定 L(N, "
            "S_min) 表达式,我们可以代入 S_min = C_min / (6 N B),然后在固定训练算力下求损 "
            "失关于 N 的极小值。对损失作为训练算力的函数,我们预测为 "
            "L(C_min) = (C_c^min / C_min)^{α_C^min},其中 α_C^min ≡ 1 / (1/α_S + 1/α_B + "
            "1/α_N) ≈ 0.054,与图 4 中得到的指数吻合得极好。我们还预测 N(C_min) ∝ "
            "C_min^{α_C^min / α_N} ≈ C_min^{0.71},这与最优模型规模图中显示的尺度在百分之几 "
            "内一致。本文给出的尺度定律为语言建模性能提供了一个可预测的框架。"},

        {"type": "h2", "text": "6.3 Contradictions and a Conjecture | 矛盾与猜想"},

        {"type": "p", "en":
            "We observe no signs of deviation from straight power-law trends at large values of "
            "compute, data, or model size. Our trends must eventually level off, though, since "
            "natural language has non-zero entropy. Indeed, the trends for compute-efficient "
            "training described in this section already contain an apparent contradiction. At "
            "scales several orders of magnitude above those documented here, the performance "
            "predicted by the L(C_min) scaling law decreases below what should be possible "
            "given the slow growth in training data with compute.",
         "zh":
            "在大算力、大数据或大模型处,我们没有观察到直线幂律趋势出现偏离的迹象。然而,这 "
            "些趋势最终必然趋于平缓,因为自然语言具有非零的熵。事实上,本节所述的算力高效 "
            "训练趋势已经包含了一个明显的矛盾:在比本文研究范围高几个数量级的尺度上, "
            "L(C_min) 尺度律所预测的性能会降低到与训练数据随算力缓慢增长所能支持的最低水 "
            "平之下。"},

        {"type": "p", "en":
            "Since the amount of data used by compute-efficient training grows slowly with "
            "the compute budget, the performance predicted by L(C_min) eventually hits a "
            "lower bound set by the L(D) power law. To keep overfitting under control, the "
            "results of Section 4 imply that we should scale the dataset size as D ∝ N^{0.74} "
            "∝ C_min^{0.54} where we have used the compute-efficient N(C_min).",
         "zh":
            "由于算力高效训练所使用的数据量随算力预算增长缓慢,L(C_min) 所预测的性能最终会 "
            "触及由 L(D) 幂律设定的下界。为控制过拟合,第 4 节的结果表明数据规模应按 "
            "D ∝ N^{0.74} ∝ C_min^{0.54} 增长(其中使用了算力高效的 N(C_min))。"},

        {"type": "p", "en":
            "Let us compare this to the data requirements of compute-efficient training. If we "
            "train at the critical batch size (i.e. C = 2 C_min) and never re-use data during "
            "training, we find that data usage grows with compute as D(C_min) ≈ (4 × 10¹⁰ "
            "tokens) · (C_min / PF-Day)^{0.26}. This is the maximum rate at which the dataset "
            "size can productively grow with compute, since it means that we are only training "
            "for a single epoch. But it grows the dataset much more slowly than in the "
            "overfitting relation. It appears to imply that compute-efficient training will "
            "eventually run into a problem with overfitting, even if the training process never "
            "re-uses any data!",
         "zh":
            "让我们将其与算力高效训练的数据需求作比较。如果我们在临界批大小下训练(即 C = "
            "2 C_min),且训练过程中不重复使用数据,则可发现数据用量随算力的增长为 "
            "D(C_min) ≈ (4 × 10¹⁰ tokens) · (C_min / PF-Day)^{0.26}。这是数据集规模能够有效地 "
            "随算力增长的最大速率,因为这意味着我们仅对数据训练一个 epoch。但其增速仍远慢于 "
            "前面给出的过拟合关系。这似乎意味着,即便训练过程从不重复使用数据,算力高效的训 "
            "练最终也会遇到过拟合的问题。"},

        {"type": "p", "en":
            "According to our basic power laws, we expect that when we are bottlenecked by the "
            "dataset size (i.e. by overfitting), the loss should scale as L(D) ∝ D^{−0.095}. "
            "This implies that the loss would scale with compute as L(D(C_min)) ∝ C_min^{−0.03} "
            "once we are data-limited. Once again, we have a contradiction, as this will "
            "eventually intersect with our prediction for L(C_min), where we found a scaling "
            "L(C_min) ∝ C_min^{−0.050}. The intersection point of L(D(C_min)) and L(C_min) "
            "occurs at C* ~ 10⁴ PF-Days, N* ~ 10¹² parameters, D* ~ 10¹² tokens, L* ~ 1.7 "
            "nats/token, though the numerical values are highly uncertain, varying by an order "
            "or magnitude in either direction depending on the precise values of the exponents.",
         "zh":
            "根据基本幂律,我们预期当训练被数据规模(即过拟合)所限制时,损失应按 L(D) ∝ "
            "D^{−0.095} 缩放。这意味着在数据受限情形下,损失随算力的缩放为 L(D(C_min)) ∝ "
            "C_min^{−0.03}。我们再次得到一个矛盾:它最终会与 L(C_min) 的预测(L(C_min) ∝ "
            "C_min^{−0.050})相交。L(D(C_min)) 与 L(C_min) 的交点出现在 C* ≈ 10⁴ PF-Days、"
            "N* ≈ 10¹² 参数、D* ≈ 10¹² tokens、L* ≈ 1.7 nats/token 处;但具体数值高度不确定, "
            "其数量级可能因指数取值不同而上下波动一个量级。"},

        {"type": "p", "en":
            "The most obvious interpretation is that our scaling laws break down at or before "
            "we reach this point, which is still many orders of magnitude away in both compute "
            "and model size. One might also conjecture that this intersection point has a "
            "deeper meaning. If we cannot increase the model size beyond N* without "
            "qualitatively different data requirements, perhaps this means that once we reach "
            "C_min* and N*, we have extracted all of the reliable information available in "
            "natural language data. In this interpretation, L* would provide a rough estimate "
            "for the entropy-per-token of natural language. In this scenario, we would expect "
            "the loss trend to level off at or before L*.",
         "zh":
            "最直接的解释是:本文的尺度定律会在到达这一交点之前(或恰好在交点处)失效——而 "
            "该交点在算力和模型规模上都还距离我们许多个数量级。另一种猜想是:这个交点具有更 "
            "深层的含义。若我们不能在不对数据要求产生质的改变的前提下把模型规模扩大到 N* 之 "
            "外,那么这或许意味着,一旦我们达到 C_min* 与 N*,我们就已提取出了自然语言数据中 "
            "所有可被可靠获取的信息。按照这种解读,L* 将提供自然语言每 token 熵的一个粗略 "
            "估计。在此情境下,我们会预期损失趋势在 L* 处或之前趋于平缓。"},

        {"type": "h1", "text": "7. Related Work | 相关工作"},

        {"type": "p", "en":
            "Power laws can arise from a wide variety of sources. Power-law scalings with "
            "model and dataset size in density estimation and in random forest models may be "
            "connected with our results. These models suggest that power-law exponents may have "
            "a very rough interpretation as the inverse of the number of relevant features "
            "in the data. Some early work found power-law scalings between performance and "
            "dataset size. More recent work also investigated scaling between model size and "
            "data size; their work is perhaps the closest to ours in the literature. Note, "
            "however, that one of them found super-linear scaling of dataset size with model "
            "size, whereas we find a sub-linear scaling.",
         "zh":
            "幂律可以来自多种多样的来源。密度估计以及随机森林模型中模型与数据集规模的幂律 "
            "缩放,可能与本文结果相关。这些模型表明,幂律指数可以被粗略地理解为数据中相关 "
            "特征数的倒数。早期一些工作发现了性能与数据集规模之间的幂律缩放;近期的一些工 "
            "作研究了模型规模与数据规模之间的尺度关系,这可能是文献中与我们最接近的工作。 "
            "不过,需要指出的是,其中一项工作发现数据集规模相对模型规模呈超线性缩放,而我们 "
            "发现的是次线性缩放。"},

        {"type": "p", "en":
            "There are some parallels between our findings on optimal allocation of compute "
            "and other recent work, including power-law learning curves. EfficientNets also "
            "appear to obey an approximate power-law relation between accuracy and model size. "
            "Very recent work studies scaling with both dataset size and model size for a "
            "variety of datasets, and fits an ansatz similar to ours. EfficientNet advocates "
            "scaling depth and width exponentially (with different coefficients) for optimal "
            "performance of image models, resulting in a power-law scaling of width as a "
            "function of depth. We find that for language models this power should be roughly "
            "one when scaling up (as width/depth should remain fixed). But more importantly, "
            "we find that the precise architectural hyperparameters are unimportant compared to "
            "the overall scale of the language model. In prior work it was argued that deep "
            "models can function as ensembles of shallower models, which could potentially "
            "explain this finding.",
         "zh":
            "我们在算力最优分配方面的发现与近期其它工作(包括幂律学习曲线)存在一定的相似 "
            "性。EfficientNet 似乎也服从一个关于准确率与模型规模的近似幂律关系。非常近期的 "
            "工作针对多种数据集研究了模型与数据规模的联合缩放,并拟合了一个与我们类似的拟 "
            "设。EfficientNet 主张对图像模型以指数方式(不同系数)同时缩放深度与宽度,从而得 "
            "到宽度作为深度函数的幂律关系。我们发现,对于语言模型,在扩展时这个幂指数应大致 "
            "为 1(即宽度/深度保持不变)。但更重要的是,我们发现精确的架构超参数与语言模型的 "
            "总尺度相比并不重要。此前有工作认为,深度模型可以看作是若干浅层模型的集成,这 "
            "或许能解释本文的发现。"},

        {"type": "p", "en":
            "Some studies fix computation per data example, which tends to scale in proportion "
            "to the number of model parameters, whereas we investigate scaling with both model "
            "size and the quantity of training computation. Various works have investigated "
            "generalization in highly overparameterized models, finding a “jamming transition” "
            "when the model size reaches the dataset size (this may require training many "
            "orders of magnitude beyond typical practice, and in particular does not use early "
            "stopping). We do not observe such a transition, and find that the necessary "
            "training data scales sublinearly in the model size. Expansions in the model size, "
            "particularly at large width, may provide a useful framework for thinking about "
            "some of our scaling relations. Our results on optimization, such as the shape of "
            "learning curves, can likely be explained using a noisy quadratic model, which can "
            "provide quite accurate predictions in realistic settings. Making this connection "
            "quantitative will require a characterization of the Hessian spectrum.",
         "zh":
            "一些研究固定每个数据样本的计算量,其规模往往与模型参数量成正比;而我们同时考察 "
            "了模型规模与训练计算量两者的缩放。已有若干工作研究了高度过参数化模型的泛化, "
            "发现当模型规模达到数据集规模时会出现堵塞相变(jamming transition)(这可能需要 "
            "比通常做法多若干数量级的训练步,且并未使用提前停止)。我们并未观察到这一相变, "
            "并发现所需的训练数据按模型规模呈次线性增长。模型规模上的展开,特别是大宽度下的 "
            "展开,可能为理解我们的某些尺度关系提供一个有用的框架。我们关于优化的结果(例如 "
            "学习曲线的形状)很可能可以用带噪二次模型来解释,该模型能在现实设置下给出相当准 "
            "确的预测。把这层联系变得定量,需要对 Hessian 谱进行刻画。"},

        {"type": "h1", "text": "8. Discussion | 讨论"},

        {"type": "p", "en":
            "We have observed consistent scalings of language model log-likelihood loss with "
            "non-embedding parameter count N, dataset size D, and optimized training computation "
            "C_min, as encapsulated in the L(N, D) and L(N, S) equations. Conversely, we find "
            "very weak dependence on many architectural and optimization hyperparameters. Since "
            "scalings with N, D, C_min are power-laws, there are diminishing returns with "
            "increasing scale.",
         "zh":
            "我们已经观察到语言模型对数似然损失与非嵌入参数量 N、数据集规模 D 以及优化后 "
            "的训练算力 C_min 之间存在一致的尺度关系,这些关系被 L(N, D) 与 L(N, S) 公式所 "
            "概括。反过来,我们发现性能对许多架构与优化超参数的依赖非常弱。由于 N、D、C_min "
            "的缩放都是幂律,因此随着尺度增大,回报会递减。"},

        {"type": "p", "en":
            "We were able to precisely model the dependence of the loss on N and D, and "
            "alternatively on N and S, when these parameters are varied simultaneously. We used "
            "these relations to derive the compute scaling, magnitude of overfitting, early "
            "stopping step, and data requirements when training large language models. So our "
            "scaling relations go beyond mere observation to provide a predictive framework. "
            "One might interpret these relations as analogues of the ideal gas law, which "
            "relates the macroscopic properties of a gas in a universal way, independent of "
            "most of the details of its microscopic constituents.",
         "zh":
            "我们能够精确刻画同时变化 N 与 D(以及 N 与 S)时损失对它们的依赖。我们利用这些 "
            "关系,推导了训练大语言模型时的算力缩放、过拟合程度、提前停止的步数以及数据需 "
            "求。因此,本文给出的尺度关系不只是简单的观察,而是提供了一个可预测的框架。我 "
            "们可以把这种关系类比为理想气体定律:它以一种普适的方式刻画气体的宏观性质,与 "
            "其微观组分的多数细节无关。"},

        {"type": "p", "en":
            "It is natural to conjecture that the scaling relations will apply to other "
            "generative modeling tasks with a maximum likelihood loss, and perhaps in other "
            "settings as well. To this purpose, it will be interesting to test these relations "
            "on other domains, such as images, audio, and video models, and perhaps also for "
            "random network distillation. At this point we do not know which of our results "
            "depend on the structure of natural language data, and which are universal. It "
            "would also be exciting to find a theoretical framework from which the scaling "
            "relations can be derived: a “statistical mechanics” underlying the "
            "“thermodynamics” we have observed. Such a theory might make it possible to derive "
            "other more precise predictions, and provide a systematic understanding of the "
            "limitations of the scaling laws.",
         "zh":
            "很自然地猜想:这些尺度关系也将适用于其它以最大似然损失进行训练的生成式建模任 "
            "务,甚至可能适用于更广泛的场景。为此,将这些关系在图像、音频、视频等其它领域 "
            "(以及随机网络蒸馏)上进行检验是很有意义的。目前,我们尚不清楚本文的哪些结果依 "
            "赖于自然语言数据的结构,哪些具有普适性。同样令人振奋的是,若能找到一个理论框 "
            "架,从这个框架中推导出这些尺度关系——也就是为本文观察到的热力学提供底层的统 "
            "计力学——那就更好了。这样的理论也许能让我们推导出其它更精确的预测,并对我们 "
            "的尺度定律的局限性提供系统性的理解。"},

        {"type": "p", "en":
            "In the domain of natural language, it will be important to investigate whether "
            "continued improvement on the loss translates into improvement on relevant language "
            "tasks. Smooth quantitative change can mask major qualitative improvements: “more "
            "is different”. For example, the smooth aggregate growth of the economy provides "
            "no indication of the specific technological developments that underwrite it. "
            "Similarly, the smooth improvements in language model loss may hide seemingly "
            "qualitative changes in capability.",
         "zh":
            "在自然语言领域,值得研究的问题是:损失上的持续改进是否能转化为相关语言任务上的 "
            "改进。平滑的、定量的变化可能掩盖重大的、定性的变化:多即不同。例如,经济总量 "
            "的平滑增长无法预示背后支撑它的具体技术进步;类似地,语言模型损失的平滑提升也可 "
            "能掩盖看似质的能力变化。"},

        {"type": "p", "en":
            "Our results strongly suggest that larger models will continue to perform better, "
            "and will also be much more sample efficient than has been previously appreciated. "
            "Big models may be more important than big data. In this context, further "
            "investigation into model parallelism is warranted. Deep models can be trained "
            "using pipelining, which splits parameters depth-wise between devices, but "
            "eventually requires increased batch sizes as more devices are used. Wide networks "
            "on the other hand are more amenable to parallelization, since large layers can be "
            "split between multiple workers with less serial dependency. Sparsity or branching "
            "(e.g. Inception) may allow for even faster training of large networks through "
            "increased model parallelism. And using methods that grow networks as they train, "
            "it might be possible to remain on the compute-efficient frontier for an entire "
            "training run.",
         "zh":
            "本文的结果强烈表明:更大的模型将继续表现更好,而且比此前所认识到的更加样本高 "
            "效。大模型可能比大数据更重要。在此背景下,对模型并行的进一步研究是必要的。深 "
            "度模型可以采用流水(pipelining)方式训练——将参数按深度切分到不同设备上,但在使 "
            "用更多设备时最终仍需要增大批大小。宽网络则更易于并行化,因为大型层可以被拆分 "
            "到多个 worker 上,且串行依赖更少。稀疏化或分支结构(如 Inception)或许能通过更 "
            "高的模型并行度,让大网络的训练更快。而采用让网络在训练过程中生长的方法,有可 "
            "能在整轮训练中始终保持在算力高效的前沿上。"},

        {"type": "h2", "text": "Acknowledgements | 致谢"},

        {"type": "p", "en":
            "We would like to thank Shan Carter, Paul Christiano, Jack Clark, Ajeya Cotra, "
            "Ethan Dyer, Jason Eisner, Danny Hernandez, Jacob Hilton, Brice Menard, Chris Olah, "
            "and Ilya Sutskever for discussions and for feedback on drafts of this work.",
         "zh":
            "我们感谢 Shan Carter、Paul Christiano、Jack Clark、Ajeya Cotra、Ethan Dyer、"
            "Jason Eisner、Danny Hernandez、Jacob Hilton、Brice Menard、Chris Olah 与 Ilya "
            "Sutskever 在本文撰写过程中提供的讨论与对初稿的反馈。"},

        {"type": "h1", "text": "Appendix A. Summary of Power Laws | 附录 A. 幂律汇总"},

        {"type": "p", "en":
            "For easier reference, we provide a summary of the key trends described throughout "
            "the paper.",
         "zh":
            "为便于查阅,本节汇总了文中所述的关键趋势。"},

        {"type": "table",
         "col_widths": [3.0 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm, 5.0 * cm],
         "rows": [
             ["Parameters / 参数", "Data / 数据", "Compute / 算力", "Batch Size / 批大小",
              "Equation / 公式"],
             ["N", "∞", "∞", "Fixed",
              "L(N) = (N_c / N)^{α_N}"],
             ["∞", "D", "Early stop", "Fixed",
              "L(D) = (D_c / D)^{α_D}"],
             ["Optimal", "∞", "C", "Fixed",
              "L(C) = (C_c / C)^{α_C}  (naive)"],
             ["N_opt", "D_opt", "C_min", "B << B_crit",
              "L(C_min) = (C_c^min / C_min)^{α_C^min}"],
             ["N", "D", "Early stop", "Fixed",
              "L(N, D) = [(N_c / N)^{α_N/α_D} + D_c / D]^{α_D}"],
             ["N", "∞", "S steps", "B",
              "L(N, S) = (N_c / N)^{α_N} + (S_c / S_min(S, B))^{α_S}"],
         ],
         "caption_en":
             "Table 2 — Key trend equations (summary).",
         "caption_zh":
             "表 2 —— 关键趋势公式汇总。"},

        {"type": "p", "en":
            "The empirical fitted values for these trends are:",
         "zh":
            "这些趋势的经验拟合值为:"},

        {"type": "table",
         "col_widths": [4.0 * cm, 4.0 * cm, 8.0 * cm],
         "rows": [
             ["Power Law / 幂律", "Exponent / 指数", "Scale (tokenization-dependent) / 尺度(依赖分词)"],
             ["α_N = 0.076", "—", "N_c = 8.8 × 10¹³ params (non-embed)"],
             ["α_D = 0.095", "—", "D_c = 5.4 × 10¹³ tokens"],
             ["α_C = 0.057", "—", "C_c = 1.6 × 10⁷ PF-days"],
             ["α_C^min = 0.050", "—", "C_c^min = 3.1 × 10⁸ PF-days"],
             ["α_B = 0.21", "—", "B_∗ = 2.1 × 10⁸ tokens"],
             ["α_S = 0.76", "—", "S_c = 2.1 × 10³ steps"],
         ],
         "caption_en":
             "Table 3 — Key parameters to trend fits.",
         "caption_zh":
             "表 3 —— 各趋势拟合的关键参数。"},

        {"type": "p", "en":
            "The optimal parameters for compute efficient training are given by:",
         "zh":
            "算力高效训练的最优参数为:"},

        {"type": "table",
         "col_widths": [5.5 * cm, 3.5 * cm, 6.0 * cm],
         "rows": [
             ["Compute-Efficient Value / 算力高效值", "Power Law / 幂律", "Scale / 尺度"],
             ["N_opt = N_e · C_min^{p_N}", "p_N = 0.73", "N_e = 1.3 × 10⁹ params"],
             ["B << B_crit = B_∗ / L^{1/α_B} = B_e · C_min^{p_B}", "p_B = 0.24",
              "B_e = 2.0 × 10⁶ tokens"],
             ["S_min = S_e · C_min^{p_S} (lower bound)", "p_S = 0.03",
              "S_e = 5.4 × 10³ steps"],
             ["D_opt = D_e · C_min^{p_D} (1 epoch)", "p_D = 0.27",
              "D_e = 2 × 10¹⁰ tokens"],
         ],
         "caption_en":
             "Table 4 — Trends for compute-efficient training.",
         "caption_zh":
             "表 4 —— 算力高效训练的趋势。"},

        {"type": "h1", "text": "Appendix B. Empirical Model of the Compute-Efficient Frontier | "
                              "附录 B. 算力高效前沿的经验模型"},

        {"type": "p", "en":
            "In this appendix we derive the optimal performance, model size, and number of "
            "training steps as a function of the compute budget, starting from "
            "L(N, S) = (N_c / N)^{α_N} + (S_c / S)^{α_S}. Here S represents the number of "
            "parameter updates when training at the critical batch size B(L) = B_∗ / L^{1/α_B}. "
            "We would like to determine optimal training parameters for a fixed compute "
            "budget, so we replace S = C / (6 N B(L)), where C is the number of FLOPs used "
            "in the training run. Setting ∂_N L |_C = 0 yields the condition for optimality:",
         "zh":
            "本附录中,我们从 L(N, S) = (N_c / N)^{α_N} + (S_c / S)^{α_S} 出发,推导损失、"
            "模型规模、训练步数随算力预算的最优变化关系。其中 S 是在临界批大小 "
            "B(L) = B_∗ / L^{1/α_B} 下训练时的参数更新次数。为确定固定算力预算下的最优训练 "
            "参数,我们将 S 替换为 C / (6 N B(L)),其中 C 是该训练运行所消耗的 FLOPs 数。令 "
            "∂_N L |_C = 0,得到最优性条件:"},

        {"type": "math", "en":
            "(α_N / α_S) · (N_c / N)^{α_N} = (6 B_∗ S_c · N / (L^{1/α_B} C))^{α_S}",
         "zh":
            "(α_N / α_S) · (N_c / N)^{α_N} = (6 B_∗ S_c · N / (L^{1/α_B} C))^{α_S}"},

        {"type": "p", "en":
            "Combining these equations, for compute-efficient training we should train to a "
            "fixed percentage α_N / α_S ≈ 10% above the converged loss. Eliminating N yields a "
            "power-law dependence of performance on compute: L(C) = (C_c / C)^{α_C}, where "
            "α_C = 1 / (1/α_S + 1/α_B + 1/α_N) ≈ 0.052 and C_c = 6 N_c B_∗ S_c (1 + α_N / "
            "α_S)^{1/α_S + 1/α_N} · (α_S / α_N)^{1/α_S}. Similarly, eliminating L yields "
            "N(C) / N_c = (C / C_c)^{α_C / α_N} · (1 + α_N / α_S)^{1/α_N}, and "
            "S(C) = (C_c / (6 N_c B_∗)) · (1 + α_N / α_S)^{−1/α_N} · (C / C_c)^{α_C / α_S}.",
         "zh":
            "结合这些方程可知:在算力高效训练下,我们应当训练至固定比收敛损失高 α_N / α_S ≈ "
            "10% 的水平。消去 N,得到性能关于算力的幂律依赖:L(C) = (C_c / C)^{α_C},其中 "
            "α_C = 1 / (1/α_S + 1/α_B + 1/α_N) ≈ 0.052,且 C_c = 6 N_c B_∗ S_c · (1 + α_N / "
            "α_S)^{1/α_S + 1/α_N} · (α_S / α_N)^{1/α_S}。类似地,消去 L 得到 "
            "N(C) / N_c = (C / C_c)^{α_C / α_N} · (1 + α_N / α_S)^{1/α_N},以及 "
            "S(C) = (C_c / (6 N_c B_∗)) · (1 + α_N / α_S)^{−1/α_N} · (C / C_c)^{α_C / α_S}。"},

        {"type": "p", "en":
            "Typically, researchers train models until they appear to be close to convergence. "
            "We compare the efficient training procedure to this more typical setup by defining "
            "a convergence factor f via L(N, C) = (1 + f) · L(N, ∞). For compute-efficient "
            "training we have f = α_N / α_S ≈ 10%, but researchers typically use a much "
            "smaller value, say f′ = 2%. For a fixed value of the loss, we predict "
            "N_f / N_f′ ≈ 2.7, S_f / S_f′ ≈ 0.13, C_f / C_f′ ≈ 0.35: compute-efficient "
            "training uses 7.7× fewer parameter updates, 2.7× more parameters, and 65% less "
            "compute to reach the same loss.",
         "zh":
            "通常,研究者会将模型训练至接近收敛。我们通过定义收敛因子 f 来比较算力高效训练与 "
            "这一更通常的做法:L(N, C) = (1 + f) · L(N, ∞)。对算力高效训练,f = α_N / α_S ≈ "
            "10%;而研究者通常使用更小的值,例如 f′ = 2%。在固定损失值下,我们预测 "
            "N_f / N_f′ ≈ 2.7,S_f / S_f′ ≈ 0.13,C_f / C_f′ ≈ 0.35:算力高效训练达到同一损失, "
            "使用的参数更新次数少 7.7 倍,参数量多 2.7 倍,而算力节省 65%。"},

        {"type": "h1", "text": "Appendix C. Caveats | 附录 C. 注意事项"},

        {"type": "p", "en":
            "We list some potential caveats to our analysis:",
         "zh":
            "我们在本节列出对本文分析的一些潜在注意事项:"},

        {"type": "p", "en":
            "• At present we do not have a solid theoretical understanding for any of our "
            "proposed scaling laws. The scaling relations with model size and compute are "
            "especially mysterious. It may be possible to understand scaling at very large D "
            "holding model size fixed, and also the shape of learning curves late in training, "
            "by modeling the loss with a noisy quadratic. But the scaling with D at very large "
            "model size still remains mysterious. Without a theory or a systematic "
            "understanding of the corrections to our scaling laws, it’s difficult to determine "
            "in what circumstances they can be trusted.",
         "zh":
            "• 目前,我们对所提出的任意一条尺度定律都没有坚实的理论理解。与模型规模、算力 "
            "相关的尺度关系尤其令人费解。在固定模型规模的情况下,通过用带噪二次模型来建模 "
            "损失,或许可以理解极大 D 处的尺度以及训练后期的学习曲线形状。但在极大模型规模 "
            "下,D 的尺度关系仍然神秘莫测。缺乏理论或对尺度定律修正项的系统理解,就很难判 "
            "断其在何种情况下仍可被信赖。"},

        {"type": "p", "en":
            "• We are not especially confident in the prediction of B_crit(L) for values of "
            "the loss far outside the range we have explored. Changes in B_crit could have a "
            "significant impact on trade-offs between data parallelism and the number of serial "
            "training steps required, which would have a major impact on training time.",
         "zh":
            "• 对于远在我们所考察的损失范围之外的情况,我们对 B_crit(L) 的预测并不十分有 "
            "把握。B_crit 的变化可能会显著影响数据并行与所需串行步数之间的权衡,从而对训练 "
            "时间产生重大影响。"},

        {"type": "p", "en":
            "• We did not thoroughly investigate the small data regime, and our fits for L(N, D) "
            "were poor for the smallest values of D (where an epoch corresponded to only 40 "
            "steps). Furthermore, we did not experiment with regularization and data "
            "augmentation. Improvements in these could alter our results, quantitatively or "
            "qualitatively.",
         "zh":
            "• 我们并未深入考察小数据模式,在 D 取最小值时(此时一个 epoch 仅对应 40 步),"
            "L(N, D) 的拟合较差。此外,我们也未尝试正则化与数据增强方面的实验。这些方面的改 "
            "进可能在定量乃至定性上改变我们的结果。"},

        {"type": "p", "en":
            "• We used the estimated training compute C ≈ 6 N B S, which did not include "
            "contributions proportional to n_ctx (see Section 2.1). So our scalings with "
            "compute may be confounded in practice in the regime of very large n_ctx, "
            "specifically where n_ctx ≳ 12 d_model.",
         "zh":
            "• 我们使用的是训练算力的估计 C ≈ 6 N B S,其中未包含与 n_ctx 成正比的项(参 "
            "见第 2.1 节)。因此,在 n_ctx 非常大的情形(特别是 n_ctx ≳ 12 d_model 时)中, "
            "我们对算力的尺度关系在实践中可能受到混淆。"},

        {"type": "p", "en":
            "• We tuned learning rates, and we experimented with learning rate schedules. But "
            "we may have neglected to tune some hyperparameter (e.g. initialization scale or "
            "momentum) that has an important effect on scaling.",
         "zh":
            "• 我们对学习率进行了调参,并尝试了多种学习率调度。但我们可能忽略了某些对尺度 "
            "关系有重要影响的超参数(如初始化尺度或动量)的调参。"},

        {"type": "p", "en":
            "• The optimal choice of learning rate is sensitive to the target loss. When "
            "training close to convergence, it may be necessary to use a smaller learning rate "
            "to avoid divergences. But when conducting a short training run (e.g. due to "
            "compute limitations), it may be possible to use a larger learning rate. We did "
            "not experiment with higher learning rates for training runs that did not proceed "
            "to convergence.",
         "zh":
            "• 最优学习率的选择对目标损失敏感。当训练接近收敛时,可能需要使用更小的学习率 "
            "以避免发散;而当进行短时间训练(例如受算力限制)时,则可以使用更大的学习率。我 "
            "们并未对那些未训练至收敛的运行尝试更高的学习率。"},

        {"type": "divider"},
        {"type": "note", "text":
            "Note: This is a faithful, full-text translation of the main body of the paper, "
            "plus the key appendix tables (Tables 2–4 of the Appendix). Figures have been "
            "referenced by number but not re-rendered; please consult the original paper for "
            "figures. Mathematical notation is linearized for PDF rendering (e.g., C_min, "
            "α_N, D ~ C^{0.27})."},
    ],
}