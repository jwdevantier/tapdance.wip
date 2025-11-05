#include "allocator.h"

static void* std_alloc(void* ctx, size_t size) {
    (void)ctx;
    return malloc(size);
}

static void std_free(void* ctx, void* ptr) {
    (void)ctx;
    free(ptr);
}

static void* std_realloc(void* ctx, void* ptr, size_t new_size) {
    (void)ctx;
    return realloc(ptr, new_size);
}

void tapd_stdalloc_init(Allocator *a) {
   a->alloc = std_alloc;
   a->free = std_free;
   a->realloc = std_realloc;
   a->ctx = NULL;
}

void *allocator_alloc(Allocator *a, size_t size) {
    return a->alloc(a->ctx, size);
}

void allocator_free(Allocator *a, void *ptr) {
    a->free(a->ctx, ptr);
}

void *allocator_realloc(Allocator *a, void *ptr, size_t new_size) {
    return a->realloc(a->ctx, ptr, new_size);
}
