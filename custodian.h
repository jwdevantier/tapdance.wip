#ifndef TAPDANCE_CUSTODIAN_H
#define TAPDANCE_CUSTODIAN_H
#include "allocator.h"

typedef struct CustodianEntry CustodianEntry;

typedef struct Custodian {
   /* NOTE: should probably have the parent entry here  if we want to panic and free all somehow. */
   CustodianEntry *stack;
   Allocator *a;
   struct Custodian *parent;
} Custodian;

typedef void (*CleanupFn)(void *resource);

void custodian_init(Custodian *c, Custodian *parent, Allocator *a);
void *custodian_alloc(Custodian *c, size_t size);
Custodian *custodian_child_create(Custodian *parent);
void custodian_defer(Custodian *c, void *ptr, CleanupFn f);
void custodian_shutdown(Custodian *c);

#endif /* TAPDANCE_CUSTODIAN_H */