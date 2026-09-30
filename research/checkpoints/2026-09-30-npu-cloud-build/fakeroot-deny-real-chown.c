#define _GNU_SOURCE
#include <sys/types.h>
#include <errno.h>
static int calls;
int real_chown_probe_calls(void) { return calls; }
int fchownat(int fd, const char *path, uid_t uid, gid_t gid, int flags)
{ (void)fd; (void)path; (void)uid; (void)gid; (void)flags; calls++; errno=EACCES; return -1; }
