#include <stdio.h>

static int shipping_score(int weight, int zone, int member) {
    if (weight < 0 || zone < 0 || zone > 4 || (member != 0 && member != 1)) return -1;
    int capped = weight > 120 ? 120 : weight;
    int points = (capped * (zone + 3) + 6) / 7;
    if (weight > 35) points += 8;
    if (zone == 4) points += 11;
    if (member && points >= 5) points -= 5;
    return points;
}

int main(void) {
    int weight, zone, member;
    if (scanf("%d %d %d", &weight, &zone, &member) != 3) {
        puts("invalid");
        return 0;
    }
    int points = shipping_score(weight, zone, member);
    if (points < 0) puts("invalid");
    else printf("%d:%s\n", points, points >= 45 ? "heavy" : "standard");
    return 0;
}
