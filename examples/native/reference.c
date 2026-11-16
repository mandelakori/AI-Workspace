#include <stdio.h>
#include <stdlib.h>

__declspec(dllexport) int shipping_points(int weight, int priority) {
    int points = weight < 0 ? 0 : weight * 3;
    if (priority) points += 7;
    return points > 100 ? 100 : points;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    printf("%d\n", shipping_points(atoi(argv[1]), atoi(argv[2])));
    return 0;
}
