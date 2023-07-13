假设一共编码$N$个包，当前网络丢包率为$P_{loss}$，最大发起重传次数为$K$，

求$K$次重传总共发送的包个数？

| 第$k$次重传 | 第$k$次重传发送的包个数 | 第$k$次重传丢失的包个数  | 第$k$次重传接收的包个数                   |
| ----------- | ----------------------- | ------------------------ | ----------------------------------------- |
| $k=0$       | $N$                     | $P_{loss} \cdot N$       | $(1-P_{loss}) \cdot N$                    |
| $k=1$       | $P_{loss} \cdot N$      | $P_{loss}^{2} \cdot N$   | $P_{loss} \cdot (1-P_{loss}) \cdot N$     |
| $k=2$       | $P_{loss}^{2} \cdot N$  | $P_{loss}^{3} \cdot N$   | $P_{loss}^{2} \cdot (1-P_{loss}) \cdot N$ |
| $k=K$       | $P_{loss}^{K} \cdot N$  | $P_{loss}^{K+1} \cdot N$ | $P_{loss}^{K} \cdot (1-P_{loss}) \cdot N$ |

## 第一种计算方式

$k=1,\cdots,K$求和得到重传总共发送的包个数：
$$
\begin{align}
G_{rexfer}(N, P_{loss}) &= \displaystyle \sum_{k=1}^{K} P_{loss}^{k} \cdot N \\
&= \frac{P_{loss} \cdot (1-P_{loss}^{K})}{1-P_{loss}} \cdot N
\end{align}
$$


## 第二种计算方式

第$k$次重传接收的包均重传了$k$次，且最后一次重传丢失的包重传了$K$次

得到所有的包总共重传的次数：
$$
\begin{align}
G_{rexfer}(N, P_{loss}) &= K \cdot P_{loss}^{K+1} \cdot N + \displaystyle \sum_{k=0}^{K} k \cdot P_{loss}^{k} \cdot (1-P_{loss}) \cdot N \\
&= K \cdot P_{loss}^{K+1} \cdot N + P_{loss} \cdot (1-P_{loss}) \cdot N \cdot \left(\displaystyle \sum_{k=0}^{K} k \cdot P_{loss}^{k-1}\right)
\end{align}
$$
记$P_{loss}\triangleq x$
$$
\sum_{k=0}^{K} k \cdot P_{loss}^{k-1} \triangleq \sum_{k=0}^{K} k \cdot x^{k-1}
=\sum_{k=0}^{K} f'(x),
\\
f(x) = x^{k}
\\
\\
\sum_{k=0}^{K} f'(x)=\left[\sum_{k=0}^{K} f(x)\right]'=\left[ \frac{x(1-x^K)}{1-x} \right]'
\\
=\frac{1-x^K}{(1-x)^2} - \frac{K \cdot x^K}{1-x}
$$
代入:
$$
\begin{align}
G_{rexfer}(N, x) &= K \cdot x^{K+1} \cdot N + x \cdot (1-x) \cdot N \cdot \left(\displaystyle \sum_{k=0}^{K} k \cdot x^{k-1}\right) \\
&= K \cdot x^{K+1} \cdot N + x \cdot (1-x) \cdot N \cdot \left( \frac{1-x^K}{(1-x)^2} - \frac{K \cdot x^K}{1-x} \right) \\
&= K \cdot x^{K+1} \cdot N + x \cdot N \cdot \frac{1-x^K}{1-x} - K \cdot x^{K+1} \cdot N \\
&= x \cdot N \cdot \frac{1-x^K}{1-x}
\end{align}
$$
因此
$$
\begin{align}
G_{rexfer}(N, P_{loss}) &= P_{loss} \cdot N \cdot \frac{1-P_{loss}^K}{1-P_{loss}} \\
&= \frac{P_{loss} \cdot (1-P_{loss}^{K})}{1-P_{loss}} \cdot N
\end{align}
$$
