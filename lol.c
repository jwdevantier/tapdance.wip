#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <assert.h>
#include "allocator.h"
#include "custodian.h"
#include <sys/wait.h>
// <<crowbar
// from tap import *
// >>
// <<end>>

void cleaner(void *data) {
  printf("CLEANER CALLED\n");
}

int test_program(Custodian *c) {
  custodian_alloc(c, 100);
  custodian_defer(c, NULL, cleaner);
  custodian_alloc(c, 200);
  Custodian *c2 = custodian_child_create(c);
  custodian_alloc(c2, 300);
  printf("SHOULD NOT SEE THIS\n");
  custodian_alloc(c2, 20);
  custodian_alloc(c, 50);
  printf("in-test cleaning:\n");
  custodian_shutdown(c);
  /* just to see how failure is handled.. 
     ATM because custodian_shutdown is idempotent, there's no effect on cleaning
     an empty custodian.
     Also, we see debug output (STDOUT, STDERR) from the failed test. */
  assert(1 == 2);
  return 0;
}

int test_add(Custodian *c, int x, int y, int expected) {
  assert(x + y == expected);
  return 0;
}

int test_segfault(Custodian *c) {
  *(int*)0 = 0;
  return 0;
}

// <<crowbar
// reg = TestRegistry()
// reg.add_test("test_program")
// reg.add_test(("test_add", "2, 3, 5"))
// reg.add_test("test_segfault")
// reg.add_test(("test_add", "2, 3, 6"))
// reg.add_test(("test_add", "4, 8, 12"))
// emit(tap_program(reg))
// >>
int main(void) {
   printf("TAP version 14\n");
   printf("1..5\n");
   {
      char tmpfile[] = "/tmp/tap_test_1";
      int tmpfd = mkstemp(tmpfile);
      if (tmpfd == -1) {
         printf("not ok 1 - test_program() (tmpfile creation failed)\n");
      } else {
         pid_t pid = fork();
         if (pid == 0) {
            dup2(tmpfd, STDERR_FILENO);
            dup2(tmpfd, STDOUT_FILENO);
            close(tmpfd);
            /* set timeout alarm */
            alarm(10);
            Allocator a;
            tapd_stdalloc_init(&a);
            Custodian c;
            custodian_init(&c, NULL, &a);
            int result = test_program(&c);
            custodian_shutdown(&c);
            exit(result);
         } else if (pid > 0) {
            int status;
            waitpid(pid, &status, 0);

            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
               printf("ok 1 - test_program()\n");
            } else {
               if (WIFEXITED(status)) {
                  printf("not ok 1 - test_program() (exit code: %d)\n", WEXITSTATUS(status));
               } else if (WIFSIGNALED(status)) {
                  if (WTERMSIG(status) == SIGALRM) {
                     printf("not ok 1 - test_program() (timeout after 10s)\n");
                  } else {
                     printf("not ok 1 - test_program() (killed by signal %d)\n", WTERMSIG(status));
                  }
               } else {
                  printf("not ok 1 - test_program() (unknown failure)\n");
               }
               lseek(tmpfd, 0, SEEK_SET);
               FILE *tmpfp = fdopen(tmpfd, "r");
               if (!tmpfp) {
                  fprintf(stderr, "# Failed to open test output for reading\n");
                  close(tmpfd);
               } else {
                  const size_t BUFLEN = 1024;
                  char line_buf[BUFLEN];
                  int fresh_line = 1;
                  while (fgets(line_buf, BUFLEN, tmpfp)) {
                     size_t len = strlen(line_buf);
                     if (fresh_line) {
                        printf("#: ");
                        fresh_line = 0;
                     }
                     printf("%s", line_buf);
                     /* Check if we reached end of line */
                     if (len > 0 && line_buf[len-1] == '\n') {
                        fresh_line = 1;
                     } else if (len < BUFLEN - 1) {
                        /* EOF without trailing newline - add one to preserve TAP integrity */
                        printf("\n");
                        fresh_line = 1;
                     }
                     /* else: partial line (buffer full), continue reading */
                  }
                  fclose(tmpfp);
               }
            }
            unlink(tmpfile);
         } else {
            close(tmpfd);
            unlink(tmpfile);
            printf("not ok 1 - test_program() (fork failed)\n");
         }
      }
   }
   {
      char tmpfile[] = "/tmp/tap_test_2";
      int tmpfd = mkstemp(tmpfile);
      if (tmpfd == -1) {
         printf("not ok 2 - test_add(2, 3, 5) (tmpfile creation failed)\n");
      } else {
         pid_t pid = fork();
         if (pid == 0) {
            dup2(tmpfd, STDERR_FILENO);
            dup2(tmpfd, STDOUT_FILENO);
            close(tmpfd);
            /* set timeout alarm */
            alarm(10);
            Allocator a;
            tapd_stdalloc_init(&a);
            Custodian c;
            custodian_init(&c, NULL, &a);
            int result = test_add(&c, 2, 3, 5);
            custodian_shutdown(&c);
            exit(result);
         } else if (pid > 0) {
            int status;
            waitpid(pid, &status, 0);

            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
               printf("ok 2 - test_add(2, 3, 5)\n");
            } else {
               if (WIFEXITED(status)) {
                  printf("not ok 2 - test_add(2, 3, 5) (exit code: %d)\n", WEXITSTATUS(status));
               } else if (WIFSIGNALED(status)) {
                  if (WTERMSIG(status) == SIGALRM) {
                     printf("not ok 2 - test_add(2, 3, 5) (timeout after 10s)\n");
                  } else {
                     printf("not ok 2 - test_add(2, 3, 5) (killed by signal %d)\n", WTERMSIG(status));
                  }
               } else {
                  printf("not ok 2 - test_add(2, 3, 5) (unknown failure)\n");
               }
               lseek(tmpfd, 0, SEEK_SET);
               FILE *tmpfp = fdopen(tmpfd, "r");
               if (!tmpfp) {
                  fprintf(stderr, "# Failed to open test output for reading\n");
                  close(tmpfd);
               } else {
                  const size_t BUFLEN = 1024;
                  char line_buf[BUFLEN];
                  int fresh_line = 1;
                  while (fgets(line_buf, BUFLEN, tmpfp)) {
                     size_t len = strlen(line_buf);
                     if (fresh_line) {
                        printf("#: ");
                        fresh_line = 0;
                     }
                     printf("%s", line_buf);
                     /* Check if we reached end of line */
                     if (len > 0 && line_buf[len-1] == '\n') {
                        fresh_line = 1;
                     } else if (len < BUFLEN - 1) {
                        /* EOF without trailing newline - add one to preserve TAP integrity */
                        printf("\n");
                        fresh_line = 1;
                     }
                     /* else: partial line (buffer full), continue reading */
                  }
                  fclose(tmpfp);
               }
            }
            unlink(tmpfile);
         } else {
            close(tmpfd);
            unlink(tmpfile);
            printf("not ok 2 - test_add(2, 3, 5) (fork failed)\n");
         }
      }
   }
   {
      char tmpfile[] = "/tmp/tap_test_3";
      int tmpfd = mkstemp(tmpfile);
      if (tmpfd == -1) {
         printf("not ok 3 - test_segfault() (tmpfile creation failed)\n");
      } else {
         pid_t pid = fork();
         if (pid == 0) {
            dup2(tmpfd, STDERR_FILENO);
            dup2(tmpfd, STDOUT_FILENO);
            close(tmpfd);
            /* set timeout alarm */
            alarm(10);
            Allocator a;
            tapd_stdalloc_init(&a);
            Custodian c;
            custodian_init(&c, NULL, &a);
            int result = test_segfault(&c);
            custodian_shutdown(&c);
            exit(result);
         } else if (pid > 0) {
            int status;
            waitpid(pid, &status, 0);

            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
               printf("ok 3 - test_segfault()\n");
            } else {
               if (WIFEXITED(status)) {
                  printf("not ok 3 - test_segfault() (exit code: %d)\n", WEXITSTATUS(status));
               } else if (WIFSIGNALED(status)) {
                  if (WTERMSIG(status) == SIGALRM) {
                     printf("not ok 3 - test_segfault() (timeout after 10s)\n");
                  } else {
                     printf("not ok 3 - test_segfault() (killed by signal %d)\n", WTERMSIG(status));
                  }
               } else {
                  printf("not ok 3 - test_segfault() (unknown failure)\n");
               }
               lseek(tmpfd, 0, SEEK_SET);
               FILE *tmpfp = fdopen(tmpfd, "r");
               if (!tmpfp) {
                  fprintf(stderr, "# Failed to open test output for reading\n");
                  close(tmpfd);
               } else {
                  const size_t BUFLEN = 1024;
                  char line_buf[BUFLEN];
                  int fresh_line = 1;
                  while (fgets(line_buf, BUFLEN, tmpfp)) {
                     size_t len = strlen(line_buf);
                     if (fresh_line) {
                        printf("#: ");
                        fresh_line = 0;
                     }
                     printf("%s", line_buf);
                     /* Check if we reached end of line */
                     if (len > 0 && line_buf[len-1] == '\n') {
                        fresh_line = 1;
                     } else if (len < BUFLEN - 1) {
                        /* EOF without trailing newline - add one to preserve TAP integrity */
                        printf("\n");
                        fresh_line = 1;
                     }
                     /* else: partial line (buffer full), continue reading */
                  }
                  fclose(tmpfp);
               }
            }
            unlink(tmpfile);
         } else {
            close(tmpfd);
            unlink(tmpfile);
            printf("not ok 3 - test_segfault() (fork failed)\n");
         }
      }
   }
   {
      char tmpfile[] = "/tmp/tap_test_4";
      int tmpfd = mkstemp(tmpfile);
      if (tmpfd == -1) {
         printf("not ok 4 - test_add(2, 3, 6) (tmpfile creation failed)\n");
      } else {
         pid_t pid = fork();
         if (pid == 0) {
            dup2(tmpfd, STDERR_FILENO);
            dup2(tmpfd, STDOUT_FILENO);
            close(tmpfd);
            /* set timeout alarm */
            alarm(10);
            Allocator a;
            tapd_stdalloc_init(&a);
            Custodian c;
            custodian_init(&c, NULL, &a);
            int result = test_add(&c, 2, 3, 6);
            custodian_shutdown(&c);
            exit(result);
         } else if (pid > 0) {
            int status;
            waitpid(pid, &status, 0);

            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
               printf("ok 4 - test_add(2, 3, 6)\n");
            } else {
               if (WIFEXITED(status)) {
                  printf("not ok 4 - test_add(2, 3, 6) (exit code: %d)\n", WEXITSTATUS(status));
               } else if (WIFSIGNALED(status)) {
                  if (WTERMSIG(status) == SIGALRM) {
                     printf("not ok 4 - test_add(2, 3, 6) (timeout after 10s)\n");
                  } else {
                     printf("not ok 4 - test_add(2, 3, 6) (killed by signal %d)\n", WTERMSIG(status));
                  }
               } else {
                  printf("not ok 4 - test_add(2, 3, 6) (unknown failure)\n");
               }
               lseek(tmpfd, 0, SEEK_SET);
               FILE *tmpfp = fdopen(tmpfd, "r");
               if (!tmpfp) {
                  fprintf(stderr, "# Failed to open test output for reading\n");
                  close(tmpfd);
               } else {
                  const size_t BUFLEN = 1024;
                  char line_buf[BUFLEN];
                  int fresh_line = 1;
                  while (fgets(line_buf, BUFLEN, tmpfp)) {
                     size_t len = strlen(line_buf);
                     if (fresh_line) {
                        printf("#: ");
                        fresh_line = 0;
                     }
                     printf("%s", line_buf);
                     /* Check if we reached end of line */
                     if (len > 0 && line_buf[len-1] == '\n') {
                        fresh_line = 1;
                     } else if (len < BUFLEN - 1) {
                        /* EOF without trailing newline - add one to preserve TAP integrity */
                        printf("\n");
                        fresh_line = 1;
                     }
                     /* else: partial line (buffer full), continue reading */
                  }
                  fclose(tmpfp);
               }
            }
            unlink(tmpfile);
         } else {
            close(tmpfd);
            unlink(tmpfile);
            printf("not ok 4 - test_add(2, 3, 6) (fork failed)\n");
         }
      }
   }
   {
      char tmpfile[] = "/tmp/tap_test_5";
      int tmpfd = mkstemp(tmpfile);
      if (tmpfd == -1) {
         printf("not ok 5 - test_add(4, 8, 12) (tmpfile creation failed)\n");
      } else {
         pid_t pid = fork();
         if (pid == 0) {
            dup2(tmpfd, STDERR_FILENO);
            dup2(tmpfd, STDOUT_FILENO);
            close(tmpfd);
            /* set timeout alarm */
            alarm(10);
            Allocator a;
            tapd_stdalloc_init(&a);
            Custodian c;
            custodian_init(&c, NULL, &a);
            int result = test_add(&c, 4, 8, 12);
            custodian_shutdown(&c);
            exit(result);
         } else if (pid > 0) {
            int status;
            waitpid(pid, &status, 0);

            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
               printf("ok 5 - test_add(4, 8, 12)\n");
            } else {
               if (WIFEXITED(status)) {
                  printf("not ok 5 - test_add(4, 8, 12) (exit code: %d)\n", WEXITSTATUS(status));
               } else if (WIFSIGNALED(status)) {
                  if (WTERMSIG(status) == SIGALRM) {
                     printf("not ok 5 - test_add(4, 8, 12) (timeout after 10s)\n");
                  } else {
                     printf("not ok 5 - test_add(4, 8, 12) (killed by signal %d)\n", WTERMSIG(status));
                  }
               } else {
                  printf("not ok 5 - test_add(4, 8, 12) (unknown failure)\n");
               }
               lseek(tmpfd, 0, SEEK_SET);
               FILE *tmpfp = fdopen(tmpfd, "r");
               if (!tmpfp) {
                  fprintf(stderr, "# Failed to open test output for reading\n");
                  close(tmpfd);
               } else {
                  const size_t BUFLEN = 1024;
                  char line_buf[BUFLEN];
                  int fresh_line = 1;
                  while (fgets(line_buf, BUFLEN, tmpfp)) {
                     size_t len = strlen(line_buf);
                     if (fresh_line) {
                        printf("#: ");
                        fresh_line = 0;
                     }
                     printf("%s", line_buf);
                     /* Check if we reached end of line */
                     if (len > 0 && line_buf[len-1] == '\n') {
                        fresh_line = 1;
                     } else if (len < BUFLEN - 1) {
                        /* EOF without trailing newline - add one to preserve TAP integrity */
                        printf("\n");
                        fresh_line = 1;
                     }
                     /* else: partial line (buffer full), continue reading */
                  }
                  fclose(tmpfp);
               }
            }
            unlink(tmpfile);
         } else {
            close(tmpfd);
            unlink(tmpfile);
            printf("not ok 5 - test_add(4, 8, 12) (fork failed)\n");
         }
      }
   }
   return 0;
}
// <<end>>
