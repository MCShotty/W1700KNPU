#include <stdlib.h>
#include <stdio.h>

static unsigned int allocation_call;
static unsigned int fail_call;

static void *decoder_calloc(size_t count, size_t size)
{
	if (++allocation_call == fail_call)
		return NULL;
	return calloc(count, size);
}

/* Only calloc calls in the included decoder are faulted, not process memory. */
#define calloc decoder_calloc
#include NL80211_SOURCE
#undef calloc

static void check(int condition, const char *message)
{
	if (!condition) {
		fprintf(stderr, "%s\n", message);
		exit(1);
	}
}

static void run_case(uc_vm_t *vm, const char *name, unsigned int messages,
		     unsigned int failure)
{
	request_state_t state = { .vm = vm, .spec = &nl80211_msg };
	unsigned int expected_count = messages - !!failure;
	unsigned char addr[] = { 2, 0, 0, 0, 0, 0x42 };
	uc_value_t *error;
	uc_value_t *record;
	char *result_json;
	int code;

	allocation_call = 0;
	fail_call = failure;
	set_error(0, NULL);
	for (unsigned int i = 0; i < messages; i++) {
		struct nl_msg *msg = nlmsg_alloc();
		check(msg != NULL, "fixture message allocation failed");
		check(genlmsg_put(msg, 0, 0, 0x42, 0, NLM_F_MULTI,
				  NL80211_CMD_NEW_INTERFACE, 0) != NULL, "fixture header failed");
		check(nla_put_u32(msg, NL80211_ATTR_WIPHY, 42) == 0, "fixture PHY failed");
		check(nla_put_string(msg, NL80211_ATTR_IFNAME, "external-fixture") == 0,
		      "fixture name failed");
		check(nla_put(msg, NL80211_ATTR_MAC, sizeof(addr), addr) == 0,
		      "fixture address failed");
		check(cb_reply(msg, &state) == NL_SKIP, "reply callback state failed");
		nlmsg_free(msg);
	}
	check(cb_done(NULL, &state) == NL_STOP, "completion callback failed");
	check(state.state == STATE_REPLIED, "request did not complete");
	check(allocation_call == messages, "unexpected decoder allocation footprint");
	check(ucv_array_length(state.res) == expected_count, "unexpected decoded record count");
	check(!!state.res == !!expected_count, "unexpected empty result representation");
	for (unsigned int i = 0; i < expected_count; i++) {
		uc_value_t *row = ucv_array_get(state.res, i);
		uc_value_t *mac = ucv_object_get(row, "mac", NULL);
		check(ucv_uint64_get(ucv_object_get(row, "wiphy", NULL)) == 42,
		      "external PHY was not decoded");
		check(!strcmp(ucv_string_get(mac),
			      "02:00:00:00:00:42"), "external address was not decoded");
	}
	code = last_error.code;
	check(code == ((EXPECT_ERROR && failure) ? NLE_NOMEM : 0), "decoder error propagation failed");
	error = uc_nl_error(vm, 0);
	check(!!error == !!code, "public error API lost the decoder failure");
	check(last_error.code == 0, "public error API did not clear the error");
	record = ucv_object_new(vm);
	ucv_object_add(record, "name", ucv_string_new(name));
	ucv_object_add(record, "messages", ucv_uint64_new(messages));
	ucv_object_add(record, "decoded", ucv_uint64_new(expected_count));
	ucv_object_add(record, "result_is_null", ucv_boolean_new(!state.res));
	ucv_object_add(record, "error_code", ucv_int64_new(code));
	ucv_object_add(record, "error_cleared", ucv_boolean_new(true));
	ucv_object_add(record, "result", ucv_get(state.res));
	ucv_object_add(record, "error", ucv_get(error));
	result_json = ucv_to_string(vm, record);
	printf("%s\n", result_json);
	free(result_json);
	ucv_put(record);
	ucv_put(error);
	ucv_put(state.res);
}

int main(void)
{
	uc_parse_config_t config = { 0 };
	uc_vm_t vm = { 0 };

	uc_vm_init(&vm, &config);
	run_case(&vm, "empty", 0, 0);
	run_case(&vm, "single", 1, 0);
	run_case(&vm, "single_oom", 1, 1);
	run_case(&vm, "two", 2, 0);
	run_case(&vm, "first_oom", 2, 1);
	run_case(&vm, "last_oom", 2, 2);
	uc_vm_free(&vm);
	return 0;
}
