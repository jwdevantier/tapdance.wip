#include <stdint.h>
#include <stdlib.h>
#include "allocator.h"
#include "custodian.h"
#include <stdio.h>

#define TAG_MASK       0x3
#define PTR_MASK       (~0x3ULL)
#define TAG_ALLOCATION 0
#define TAG_RESOURCE   1
#define TAG_CUSTODIAN  2

typedef struct CustodianEntry {
   struct CustodianEntry *prev;
} CustodianEntry;

typedef struct {
   void *ptr;
   void (*cleanup)(void *);
} CustodianResource;

static inline void *ptr_tag(void *ptr, int tag) {
   return (void *)((uintptr_t)ptr | (tag & TAG_MASK));
}

static inline void *ptr_untag(void *tagged_ptr) {
   return (void *)((uintptr_t) tagged_ptr & PTR_MASK);
}

static inline int ptr_tag_get(void *tagged_ptr) {
   return (int)((uintptr_t)tagged_ptr & TAG_MASK);
}

static void custodian_abort(Custodian *c);


void custodian_init(Custodian *c, Custodian *parent, Allocator *a) {
   c->stack = NULL;
   c->a = a;
   c->parent = parent;
}

void *custodian_alloc(Custodian *c, size_t size) {
   CustodianEntry *entry = allocator_alloc(c->a, size);
   if (!entry) {
      custodian_abort(c);
      return NULL;
   }
   entry->prev = ptr_tag(c->stack, TAG_ALLOCATION);
   c->stack = entry;

   return (char *)entry + sizeof(CustodianEntry);
}

Custodian *custodian_child_create(Custodian *parent) {
   CustodianEntry *entry = allocator_alloc(parent->a, sizeof(CustodianEntry) + sizeof(Custodian));
   if (!entry) {
      custodian_abort(parent);
      return NULL;
   }

   Custodian *child = (Custodian *)((char *)entry + sizeof(CustodianEntry));
   custodian_init(child, parent, parent->a);

   entry->prev = ptr_tag(parent->stack, TAG_CUSTODIAN);
   parent->stack = entry;

   return child;
}

void custodian_defer(Custodian *c, void *ptr, CleanupFn f) {
   CustodianEntry *entry = allocator_alloc(c->a, sizeof(CustodianEntry) + sizeof(CustodianResource));
   if (!entry) {
      custodian_abort(c);
      return;
   }

   CustodianResource *res = (CustodianResource *)((char *) entry + sizeof(CustodianEntry));
   res->ptr = ptr;
   res->cleanup = f;

   entry->prev = ptr_tag(c->stack, TAG_RESOURCE);
   c->stack = entry;

   return;
}

void custodian_shutdown(Custodian *c) {
   CustodianEntry *entry = c->stack;
   Allocator *a = c->a;

   while (entry) {
      CustodianEntry *prev = ptr_untag(entry->prev);
      int tag = ptr_tag_get(entry->prev);

      void *data = (char *)entry + sizeof(CustodianEntry);

      switch (tag) {
      case TAG_ALLOCATION:
         allocator_free(a, entry);
         break;
      case TAG_RESOURCE:
         {
            CustodianResource *res = (CustodianResource *)data;
            if (res->cleanup) {
               res->cleanup(res->ptr);
            }
            allocator_free(a, entry);
            break;
         }
      case TAG_CUSTODIAN:
         {
            Custodian *child = (Custodian *)data;
            custodian_shutdown(child);
            allocator_free(a, entry);
            break;
         }
      }

      entry = prev;
   }
   c->stack = NULL;
}

static void custodian_abort(Custodian *c) {
   /* something happened, traverse up the tree and initiate a shutdown of all. */
   Custodian *cur = c;
   while (cur->parent != NULL) {
      cur = cur->parent;
   }

   custodian_shutdown(cur);
   abort();
}

