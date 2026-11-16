#include <stdio.h>
#include <stdlib.h>

int shipping_points(int weight, int priority) {
    (void)weight;
    (void)priority;
    return 0;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    printf("%d\n", shipping_points(atoi(argv[1]), atoi(argv[2])));
    return 0;
}
