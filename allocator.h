#ifndef TAPDANCE_ALLOCATOR_H
#define TAPDANCE_ALLOCATOR_H
#include <stdlib.h>

typedef void *(*AllocFn)(void *ctx, size_t size);
typedef void (*FreeFn)(void *ctx, void *ptr);
typedef void *(*ReallocFn)(void *ctx, void *ptr, size_t new_size);

typedef struct {
   AllocFn alloc;
   FreeFn free;
   ReallocFn realloc;
   void *ctx; 
} Allocator;

void tapd_stdalloc_init(Allocator *a);

void *allocator_alloc(Allocator *a, size_t size);
void allocator_free(Allocator *a, void *ptr);
void *allocator_realloc(Allocator *a, void *ptr, size_t new_size);
#endif /* TAPDANCE_ALLOCATOR_H */