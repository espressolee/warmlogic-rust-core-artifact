def test_schnorr_identity():
    # Smallest possible safe prime for debugging
    P = 23
    G = 2
    Q = 22  # G=2 is generator
    x = 7
    y = pow(G, x, P)  # 7
    k = 5
    R = pow(G, k, P)  # 9

    # Challenge c (let's say c=3)
    c = 3
    s = (k + c * x) % Q  # (5 + 21) % 22 = 26 % 22 = 4

    lhs = pow(G, s, P)  # 2^4 = 16
    rhs = (R * pow(y, c, P)) % P  # 9 * (y^3) = 9 * (pow(2, 7, 23)^3)
    # y = 2^7 = 128 = 13 mod 23
    # y^3 = 13^3 = 2197. 2197 / 23 = 95.5... 95*23 = 2185. 2197 - 2185 = 12.
    # rhs = 9 * 12 = 108. 108 / 23 = 4.6... 4*23 = 92. 108 - 92 = 16.

    print(f"P={P}, G={G}, Q={Q}")
    print(f"y={y}, R={R}, c={c}, s={s}")
    print(f"lhs={lhs}, rhs={rhs}, Match={lhs == rhs}")


if __name__ == "__main__":
    test_schnorr_identity()
